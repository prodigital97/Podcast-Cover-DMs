"""Orchestration: inbound DM -> drafts -> Telegram card -> approved reply -> Instagram."""
from __future__ import annotations

import logging

from app import db
from app.drafting import REDRAFT_NUDGE, draft, infer_voice_notes
from app.instagram import InstagramClient
from app.telegram import TelegramClient

log = logging.getLogger(__name__)


async def ensure_lead(igsid: str, instagram: InstagramClient) -> dict:
    """Build the lead profile from Instagram so nobody hand-writes one.

    Runs once per lead. The messaging profile gives handle, name, and follower count;
    business_discovery (when configured, and only for professional accounts) adds the
    bio and recent captions. Anything unavailable stays unknown rather than invented.
    """
    lead = db.get_lead(igsid)
    if lead and lead.get("enriched_at"):
        return lead

    profile = await instagram.profile(igsid)
    username = profile.get("username")
    fields = {
        "handle": f"@{username}" if username else None,
        "podcast_name": profile.get("name"),
        "audience_size": str(profile["follower_count"]) if profile.get("follower_count") else None,
    }

    discovery = await instagram.business_discovery(username) if username else {}
    if discovery.get("biography"):
        fields["bio"] = discovery["biography"]
    if discovery.get("followers_count"):
        fields["audience_size"] = str(discovery["followers_count"])
    captions = [
        media.get("caption", "").strip()
        for media in (discovery.get("media") or {}).get("data", [])
        if media.get("caption")
    ]
    if captions:
        fields["about"] = "Recent posts: " + " | ".join(c[:200] for c in captions[:4])

    lead = db.upsert_lead(igsid, **fields)
    db.mark_enriched(igsid)
    return lead


async def handle_incoming(
    igsid: str, text: str, mid: str, instagram: InstagramClient, telegram: TelegramClient
) -> str | None:
    """Record an inbound DM, draft replies, and post the approval card.

    Returns the approval id, or None if the message was a duplicate delivery.
    """
    if not db.add_message(igsid, "them", text, mid or None):
        log.info("duplicate webhook delivery for mid=%s", mid)
        return None

    lead = await ensure_lead(igsid, instagram)

    lead = db.upsert_lead(igsid, voice_notes=infer_voice_notes(_recent_inbound(igsid)))

    drafts = await draft(lead, text, db.thread(igsid))
    _apply_lead_update(igsid, drafts)

    approval_id = db.create_approval(igsid, text, drafts.model_dump())
    await _post_card(approval_id, igsid, telegram)
    return approval_id


async def _post_card(approval_id: str, igsid: str, telegram: TelegramClient) -> None:
    """Post an approval card with the context that makes it decidable at a glance:
    how far into the conversation this is, and how long is left to reply."""
    message_id = await telegram.send_approval(
        db.get_lead(igsid),
        db.get_approval(approval_id),
        last_inbound_at=db.last_inbound_at(igsid),
        inbound_count=db.inbound_count(igsid),
    )
    db.set_approval_message_id(approval_id, message_id)


def _recent_inbound(igsid: str, limit: int = 8) -> list[str]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT text FROM messages WHERE igsid = ? AND direction = 'them'"
            " ORDER BY created_at DESC LIMIT ?",
            (igsid, limit),
        ).fetchall()
    return [row["text"] for row in rows]


def _apply_lead_update(igsid: str, drafts) -> None:
    """Fold the model's pipeline reading back into the lead. Nulls mean unchanged."""
    update = drafts.lead_update
    db.upsert_lead(
        igsid,
        status=drafts.stage,
        needs=update.needs,
        offered=update.offered,
        price=update.price,
        commitments=update.commitments,
    )


async def send_approved(
    approval_id: str, text: str, instagram: InstagramClient, telegram: TelegramClient
) -> None:
    """Deliver an approved reply to Instagram and close out the card."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise RuntimeError(f"no such approval: {approval_id}")
    if approval["state"] == "sent":
        raise RuntimeError("already sent")

    igsid = approval["igsid"]
    await instagram.send_text(igsid, text, last_inbound_at=db.last_inbound_at(igsid))
    db.add_message(igsid, "pronoy", text)
    db.set_approval_state(approval_id, "sent", sent_text=text)
    if approval["telegram_message_id"]:
        await telegram.resolve_card(
            approval["telegram_message_id"], db.get_lead(igsid), approval, "✅ Sent to", text
        )


async def redraft(approval_id: str, instagram: InstagramClient, telegram: TelegramClient) -> None:
    """Throw the drafts away and ask for a different angle."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise RuntimeError(f"no such approval: {approval_id}")
    igsid = approval["igsid"]
    lead = db.get_lead(igsid)

    drafts = await draft(lead, approval["incoming_text"], db.thread(igsid), nudge=REDRAFT_NUDGE)
    _apply_lead_update(igsid, drafts)

    db.set_approval_state(approval_id, "superseded")
    if approval["telegram_message_id"]:
        await telegram.resolve_card(
            approval["telegram_message_id"], lead, approval, "\U0001f504 Redrafted —"
        )

    new_id = db.create_approval(igsid, approval["incoming_text"], drafts.model_dump())
    await _post_card(new_id, igsid, telegram)


async def stage_edit(approval_id: str, text: str, telegram: TelegramClient) -> None:
    """Hold typed replacement text for confirmation instead of sending it.

    Without this step, tapping Edit and then typing anything at all in the bot
    chat fires it straight at a real prospect — including a stray note typed
    hours later, after you'd forgotten a card was open. Nothing else in this
    product reaches Instagram without an explicit tap; this closes the one gap
    where it did.
    """
    approval = db.get_approval(approval_id)
    if not approval:
        raise RuntimeError(f"no such approval: {approval_id}")
    db.set_approval_state(approval_id, "awaiting_confirm", sent_text=text)
    await telegram.ask_to_confirm(db.get_lead(approval["igsid"]), approval_id, text)


async def cancel_edit(approval_id: str, telegram: TelegramClient) -> None:
    """Put a card back to open, so an abandoned edit can't swallow later typing."""
    approval = db.get_approval(approval_id)
    if not approval:
        raise RuntimeError(f"no such approval: {approval_id}")
    db.set_approval_state(approval_id, "open")
    await telegram.send("Edit cancelled — the card is still open.")
