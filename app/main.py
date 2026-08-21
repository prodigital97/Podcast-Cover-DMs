"""Webhook service. Instagram DMs in, Telegram approvals out, approved replies back.

Nothing is ever sent to Instagram without an explicit tap in Telegram.
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, Request, Response

from app import approvals, db
from app.config import config
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
    if action in {"c", "k"} and approval["state"] not in {"awaiting_confirm", "awaiting_edit"}:
        await telegram.answer_callback(callback["id"], "Nothing pending to confirm.")
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
            await telegram.ask_for_edit(db.get_lead(approval["igsid"]), approval_id)
        elif action == "c":
            await telegram.answer_callback(callback["id"], "Sending…")
            await approvals.send_approved(
                approval_id, approval["sent_text"], instagram, telegram
            )
        elif action == "k":
            await telegram.answer_callback(callback["id"], "Cancelled.")
            await approvals.cancel_edit(approval_id, telegram)
        elif action == "r":
            await telegram.answer_callback(callback["id"], "Redrafting…")
            await approvals.redraft(approval_id, instagram, telegram)
        elif action == "x":
            db.set_approval_state(approval_id, "skipped")
            await telegram.answer_callback(callback["id"], "Skipped.")
            if approval["telegram_message_id"]:
                await telegram.resolve_card(
                    approval["telegram_message_id"],
                    db.get_lead(approval["igsid"]), approval, "\U0001f6ab Skipped —",
                )
    except Exception as exc:
        log.exception("callback %s failed", action)
        await telegram.send(f"⚠️ {exc}")


async def _process_message(message: dict) -> None:
    """A typed reply. Only meaningful while an approval is awaiting edited text."""
    if not _authorised((message.get("chat") or {}).get("id")):
        return
    text = (message.get("text") or "").strip()
    if not text:
        return

    approval = db.awaiting_edit()
    if not approval:
        await telegram.send("No draft is waiting on an edit right now.")
        return

    try:
        # Staged for confirmation, never sent straight off a typed line.
        await approvals.stage_edit(approval["id"], text, telegram)
    except Exception as exc:
        log.exception("staging an edited reply failed")
        db.set_approval_state(approval["id"], "open")
        await telegram.send(f"⚠️ {exc}")
