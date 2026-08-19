"""Webhook service. Instagram DMs in, Telegram approvals out, approved replies back.

Nothing is ever sent to Instagram without an explicit tap in Telegram.
"""
from __future__ import annotations

import csv
import hmac
import io
import logging
import pathlib
import time
from typing import Any
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app import approvals, db
from app.config import config
from app.drafting import REDRAFT_NUDGE, draft, infer_voice_notes
from app.instagram import InstagramClient, parse_events, verify_challenge, verify_signature
from app.telegram import TelegramClient, parse_callback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# httpx logs every outgoing request at INFO, full URL included. Telegram's Bot
# API puts the bot token directly in the URL path, and our own Instagram
# client passes its access token as a URL query parameter — either would land
# the credential in plaintext in the server log at the default INFO level.
# Only this app's own "podcast-cover-dms" logger needs INFO; httpx's request
# tracing is a debugging aid, not something to run at INFO in production.
logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger("podcast-cover-dms")

instagram = InstagramClient()
telegram = TelegramClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    db.init()
    yield
    await instagram.aclose()
    await telegram.aclose()


app = FastAPI(title="Podcast Cover DMs", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Instagram -------------------------------------------------------------

@app.get("/webhooks/instagram")
async def instagram_verify(request: Request) -> Response:
    challenge = verify_challenge(dict(request.query_params))
    if challenge is None:
        return Response("verification failed", status_code=403)
    return Response(challenge, media_type="text/plain")


@app.post("/webhooks/instagram")
async def instagram_webhook(request: Request, background: BackgroundTasks) -> Response:
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("x-hub-signature-256")):
        log.warning("rejected Instagram webhook with a bad signature")
        return Response("bad signature", status_code=403)

    for event in parse_events(await request.json()):
        background.add_task(_process_incoming, event["igsid"], event["text"], event["mid"])
    # Meta retries anything slower than a few seconds, so acknowledge before drafting.
    return Response(status_code=200)


async def _process_incoming(igsid: str, text: str, mid: str) -> None:
    try:
        await approvals.handle_incoming(igsid, text, mid, instagram, telegram)
    except Exception:
        log.exception("failed to draft a reply for %s", igsid)
        try:
            await telegram.send(f"⚠️ Couldn't draft a reply to {igsid}. Check the logs.")
        except Exception:
            log.exception("could not report the drafting failure to Telegram")


# --- Telegram --------------------------------------------------------------

@app.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", config.telegram_secret()):
        log.warning("rejected Telegram webhook with a bad secret token")
        return Response(status_code=403)

    update = await request.json()
    if callback := update.get("callback_query"):
        background.add_task(_process_callback, callback)
    elif message := update.get("message"):
        background.add_task(_process_message, message)
    return Response(status_code=200)


def _authorised(chat_id: object) -> bool:
    return str(chat_id) == str(config.TELEGRAM_CHAT_ID)


async def _process_callback(callback: dict) -> None:
    message = callback.get("message") or {}
    if not _authorised((message.get("chat") or {}).get("id")):
        log.warning("ignoring callback from unauthorised chat")
        return

    parsed = parse_callback(callback.get("data", ""))
    if not parsed:
        await telegram.answer_callback(callback["id"], "Unrecognised button.")
        return
    action, approval_id, index = parsed

    approval = db.get_approval(approval_id)
    if not approval:
        await telegram.answer_callback(callback["id"], "That draft is gone.")
        return
    if approval["state"] in {"sent", "skipped", "superseded"}:
        await telegram.answer_callback(callback["id"], f"Already {approval['state']}.")
        return

    try:
        if action == "s":
            await telegram.answer_callback(callback["id"], "Sending…")
            await approvals.send_approved(
                approval_id, approval["drafts"][index]["text"], instagram, telegram
            )
        elif action == "e":
            db.set_approval_state(approval_id, "awaiting_edit")
            await telegram.answer_callback(callback["id"], "Reply with your text.")
            await telegram.send(
                "✏️ Reply to this message with the text to send instead.", force_reply=True
            )
        elif action == "r":
            await telegram.answer_callback(callback["id"], "Redrafting…")
            await approvals.redraft(approval_id, instagram, telegram)
        elif action == "x":
            db.set_approval_state(approval_id, "skipped")
            await telegram.answer_callback(callback["id"], "Skipped.")
            if approval["telegram_message_id"]:
                await telegram.clear_keyboard(approval["telegram_message_id"], "\U0001f6ab Skipped.")
    except Exception as exc:
        log.exception("callback %s failed", action)
        await telegram.send(f"⚠️ {exc}")


async def _process_message(message: dict) -> None:
    """A typed reply. If an approval is awaiting edit, send edited text.
    Otherwise, draft 3 strategic reply options for the typed or pasted message."""
    if not _authorised((message.get("chat") or {}).get("id")):
        return
    text = (message.get("text") or "").strip()
    if not text:
        return

    if text.lower() in {"/start", "/help"}:
        await telegram.send(
            "👋 <b>Podcast Cover DM Copilot Active!</b>\n\n"
            "• Incoming Instagram DMs arrive here automatically.\n"
            "• You can also <b>paste any DM thread or message here right now</b> to draft 3 strategic reply options instantly!"
        )
        return

    approval = db.awaiting_edit()
    if approval:
        try:
            await approvals.send_approved(approval["id"], text, instagram, telegram)
        except Exception as exc:
            log.exception("sending an edited reply failed")
            db.set_approval_state(approval["id"], "open")
            await telegram.send(f"⚠️ {exc}")
        return

    try:
        await telegram.send("🤖 Drafting 3 strategic reply options with Gemini…")
        await approvals.handle_telegram_draft(text, telegram)
    except Exception as exc:
        log.exception("on-demand drafting failed in Telegram")
        await telegram.send(f"⚠️ Drafting failed: {exc}")


# --- Dashboard & CRM REST API ----------------------------------------------

from fastapi.staticfiles import StaticFiles

STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
@app.get("/dashboard")
async def dashboard() -> Response:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return Response("Dashboard UI loading... static files not yet initialized.", media_type="text/plain")


@app.get("/api/leads")
async def api_list_leads() -> dict[str, Any]:
    leads = db.list_leads()
    return {"leads": leads, "count": len(leads)}


@app.post("/api/leads")
async def api_create_lead(payload: dict[str, Any]) -> dict[str, Any]:
    handle = (payload.get("handle") or "").strip()
    igsid = payload.get("igsid") or (f"lead_{handle.lstrip('@')}" if handle else f"lead_{uuid.uuid4().hex[:8]}")
    
    lead_data = {
        "handle": f"@{handle.lstrip('@')}" if handle else None,
        "podcast_name": payload.get("podcast_name"),
        "bio": payload.get("bio"),
        "audience_size": str(payload["audience_size"]) if payload.get("audience_size") else None,
        "notes": payload.get("notes", ""),
        "status": payload.get("status", "first_contact"),
    }
    lead = db.upsert_lead(igsid, **lead_data)
    
    initial_message = (payload.get("initial_message") or "").strip()
    drafts = None
    if initial_message:
        db.add_message(igsid, "them", initial_message)
        drafts_obj = await draft(lead, initial_message, db.thread(igsid))
        approvals._apply_lead_update(igsid, drafts_obj)
        approval_id = db.create_approval(igsid, initial_message, drafts_obj.model_dump())
        lead = db.get_lead(igsid)
        drafts = drafts_obj.model_dump()
        drafts["approval_id"] = approval_id

    return {"success": True, "igsid": igsid, "lead": lead, "drafts": drafts}


@app.get("/api/leads/{igsid}")
async def api_get_lead(igsid: str) -> dict[str, Any]:
    lead = db.get_lead(igsid)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    messages = db.get_lead_messages(igsid)
    open_approval = db.open_approval_for(igsid)
    return {"lead": lead, "messages": messages, "open_approval": open_approval}


@app.put("/api/leads/{igsid}")
async def api_update_lead(igsid: str, payload: dict[str, Any]) -> dict[str, Any]:
    lead = db.get_lead(igsid)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updated = db.upsert_lead(igsid, **payload)
    return {"success": True, "lead": updated}


@app.delete("/api/leads/{igsid}")
async def api_delete_lead(igsid: str) -> dict[str, Any]:
    deleted = db.delete_lead(igsid)
    return {"success": deleted}


@app.post("/api/leads/{igsid}/messages")
async def api_add_message(igsid: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    direction = payload.get("direction", "them")
    if direction not in {"them", "pronoy"}:
        direction = "them"

    lead = db.get_lead(igsid)
    if not lead:
        lead = db.upsert_lead(igsid, handle=igsid, status="first_contact")

    db.add_message(igsid, direction, text)

    drafts = None
    if direction == "them":
        lead = db.upsert_lead(igsid, voice_notes=infer_voice_notes(approvals._recent_inbound(igsid)))
        drafts_obj = await draft(lead, text, db.thread(igsid))
        approvals._apply_lead_update(igsid, drafts_obj)
        approval_id = db.create_approval(igsid, text, drafts_obj.model_dump())
        lead = db.get_lead(igsid)
        drafts = drafts_obj.model_dump()
        drafts["approval_id"] = approval_id
    elif direction == "pronoy":
        open_app = db.open_approval_for(igsid)
        if open_app:
            db.set_approval_state(open_app["id"], "sent", sent_text=text)

    messages = db.get_lead_messages(igsid)
    return {"success": True, "lead": lead, "messages": messages, "drafts": drafts}


@app.post("/api/leads/{igsid}/redraft")
async def api_redraft(igsid: str) -> dict[str, Any]:
    lead = db.get_lead(igsid)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    open_app = db.open_approval_for(igsid)
    incoming_text = open_app["incoming_text"] if open_app else "Inquiry about podcast cover design and branding"
    
    drafts_obj = await draft(lead, incoming_text, db.thread(igsid), nudge=REDRAFT_NUDGE)
    approvals._apply_lead_update(igsid, drafts_obj)
    
    if open_app:
        db.set_approval_state(open_app["id"], "superseded")
    
    new_approval_id = db.create_approval(igsid, incoming_text, drafts_obj.model_dump())
    drafts = drafts_obj.model_dump()
    drafts["approval_id"] = new_approval_id
    return {"success": True, "drafts": drafts, "lead": db.get_lead(igsid)}


@app.post("/api/leads/{igsid}/approve")
async def api_approve_draft(igsid: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = (payload.get("text") or "").strip()
    approval_id = payload.get("approval_id")
    if not text:
        raise HTTPException(status_code=400, detail="Draft text required")
    
    if approval_id:
        db.set_approval_state(approval_id, "sent", sent_text=text)
    
    db.add_message(igsid, "pronoy", text)
    messages = db.get_lead_messages(igsid)
    lead = db.get_lead(igsid)
    return {"success": True, "lead": lead, "messages": messages}


@app.get("/api/export/csv")
async def api_export_csv() -> Response:
    rows = db.get_export_rows()
    if not rows:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Instagram ID / Handle", "Podcast Name", "Bio / Niche", "Status / Stage", "Conversion Probability (%)", "Full Chat History"])
        csv_content = output.getvalue()
    else:
        output = io.StringIO()
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        csv_content = output.getvalue()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=podcast_cover_leads_{int(time.time())}.csv"
        },
    )
