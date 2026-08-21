"""Telegram bot: the approval surface.

This is the only interface Pronoy actually touches, so the card has to answer
the questions he'd otherwise have to go and look up: how long is left to
reply, how long their message was against ours, and whether this is a cold
opener or the middle of a conversation.
"""
from __future__ import annotations

import html
import logging
import time
from typing import Any

import httpx

from app.config import config
from app.instagram import STANDARD_WINDOW_SECONDS

log = logging.getLogger(__name__)

TONE_LABELS = {"warm": "Warm", "direct": "Direct", "low_pressure": "Low pressure"}
# Kept short: three buttons share one row on a phone.
TONE_BUTTONS = {"warm": "Warm", "direct": "Direct", "low_pressure": "Low-key"}
STAGE_LABELS = {
    "first_contact": "First contact",
    "building": "Building",
    "green_light": "Green light",
    "soft_no": "Soft no",
    "hard_no": "Hard no",
    "active_client": "Active client",
}
NUMERALS = ["1️⃣", "2️⃣", "3️⃣"]


def humanise_audience(value: str | None) -> str | None:
    """18000 -> 18k. Leaves anything non-numeric alone."""
    if not value:
        return None
    digits = str(value).replace(",", "").strip()
    if not digits.isdigit():
        return str(value)
    count = int(digits)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}m".replace(".0m", "m")
    if count >= 1_000:
        return f"{count / 1_000:.1f}k".replace(".0k", "k")
    return str(count)


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def window_note(last_inbound_at: float | None, *, now: float | None = None) -> str | None:
    """How long is left to reply, phrased so it reads as urgency, not trivia.

    Instagram only allows a reply within 24h of their last message. The service
    enforces that on send; this is what stops it being a surprise.
    """
    if not last_inbound_at:
        return None
    remaining = STANDARD_WINDOW_SECONDS - ((now or time.time()) - last_inbound_at)
    if remaining <= 0:
        return "⚠️ reply window closed"
    hours, minutes = int(remaining // 3600), int((remaining % 3600) // 60)
    if hours >= 12:
        return f"⏳ {hours}h left"
    if hours >= 1:
        return f"⏳ {hours}h {minutes}m left"
    return f"⚠️ {minutes}m left"


def _words(text: str) -> int:
    return len(text.split())


def approval_text(
    lead: dict[str, Any],
    approval: dict[str, Any],
    *,
    last_inbound_at: float | None = None,
    inbound_count: int | None = None,
    now: float | None = None,
) -> str:
    """The card body. HTML parse mode — every interpolated value is escaped."""
    handle = html.escape(lead.get("handle") or lead["igsid"])
    stage = STAGE_LABELS.get(approval["stage"], approval["stage"])

    header = [f"<b>{handle}</b>"]
    if audience := humanise_audience(lead.get("audience_size")):
        header.append(html.escape(audience))
    header.append(stage)

    context = []
    if inbound_count:
        context.append("their first message" if inbound_count == 1
                       else f"their {ordinal(inbound_count)} message")
    if note := window_note(last_inbound_at, now=now):
        context.append(note)

    incoming = approval["incoming_text"]
    lines = [f"\U0001f4e9 {' · '.join(header)}"]
    if context:
        lines.append(f"<i>{' · '.join(context)}</i>")
    lines += [
        "",
        f"<blockquote>{html.escape(incoming)}</blockquote>",
        f"<i>{_words(incoming)} words</i>",
        "",
        f"<i>{html.escape(approval['read'])}</i>",
        "",
    ]

    for index, draft in enumerate(approval["drafts"][:3]):
        label = TONE_LABELS.get(draft["tone"], draft["tone"])
        lines.append(
            f"{NUMERALS[index]} <b>{label}</b> · <i>{_words(draft['text'])} words</i>\n"
            f"{html.escape(draft['text'])}\n"
        )
    return "\n".join(lines).strip()


def resolved_text(lead: dict[str, Any], approval: dict[str, Any], outcome: str,
                  sent_text: str | None = None) -> str:
    """What a handled card collapses to.

    Drops the three drafts — once a decision is made they are noise, and the
    scrollback is far more readable as a list of what was said and what went
    back than as a wall of rejected options.
    """
    handle = html.escape(lead.get("handle") or lead["igsid"])
    lines = [
        f"{outcome} <b>{handle}</b>",
        "",
        f"<blockquote>{html.escape(approval['incoming_text'])}</blockquote>",
    ]
    if sent_text:
        lines += ["", f"↳ {html.escape(sent_text)}"]
    return "\n".join(lines)


def confirm_text(lead: dict[str, Any], text: str) -> str:
    handle = html.escape(lead.get("handle") or lead["igsid"])
    return (
        f"✏️ Send this to <b>{handle}</b>?\n\n"
        f"<blockquote>{html.escape(text)}</blockquote>\n"
        f"<i>{_words(text)} words</i>"
    )


def approval_keyboard(approval_id: str, drafts: list[dict[str, Any]]) -> dict[str, Any]:
    """Buttons name the tone, not just a number.

    On a phone the drafts have scrolled off-screen by the time you reach the
    buttons, so "Send 2" means nothing without scrolling back up.
    """
    send_row = [
        {
            "text": f"{i + 1} · {TONE_BUTTONS.get(draft['tone'], draft['tone'])}",
            "callback_data": f"s:{approval_id}:{i}",
        }
        for i, draft in enumerate(drafts[:3])
    ]
    return {
        "inline_keyboard": [
            send_row,
            [
                {"text": "✏️ Edit", "callback_data": f"e:{approval_id}:0"},
                {"text": "\U0001f504 Redraft", "callback_data": f"r:{approval_id}:0"},
                {"text": "\U0001f6ab Skip", "callback_data": f"x:{approval_id}:0"},
            ],
        ]
    }


def confirm_keyboard(approval_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [[
            {"text": "✅ Send", "callback_data": f"c:{approval_id}:0"},
            {"text": "✖️ Cancel", "callback_data": f"k:{approval_id}:0"},
        ]]
    }


def cancel_keyboard(approval_id: str) -> dict[str, Any]:
    return {"inline_keyboard": [[
        {"text": "✖️ Cancel edit", "callback_data": f"k:{approval_id}:0"},
    ]]}


ACTIONS = {"s", "e", "r", "x", "c", "k"}


def parse_callback(data: str) -> tuple[str, str, int] | None:
    """"s:<approval_id>:<index>" -> ("s", approval_id, index). 64-byte budget."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in ACTIONS:
        return None
    try:
        return parts[0], parts[1], int(parts[2])
    except ValueError:
        return None


class TelegramClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=20)

    async def _call(self, method: str, **payload: Any) -> dict[str, Any]:
        response = await self._client.post(
            f"https://api.telegram.org/bot{config.telegram_token()}/{method}", json=payload
        )
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {body}")
        return body.get("result", {})

    async def send_approval(
        self,
        lead: dict,
        approval: dict,
        *,
        last_inbound_at: float | None = None,
        inbound_count: int | None = None,
    ) -> int:
        result = await self._call(
            "sendMessage",
            chat_id=config.TELEGRAM_CHAT_ID,
            text=approval_text(
                lead, approval,
                last_inbound_at=last_inbound_at, inbound_count=inbound_count,
            ),
            parse_mode="HTML",
            reply_markup=approval_keyboard(approval["id"], approval["drafts"]),
        )
        return int(result["message_id"])

    async def send(self, text: str, *, reply_markup: dict | None = None) -> int:
        payload: dict[str, Any] = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await self._call("sendMessage", **payload)
        return int(result["message_id"])

    async def ask_for_edit(self, lead: dict, approval_id: str) -> int:
        handle = html.escape(lead.get("handle") or lead["igsid"])
        return await self.send(
            f"✏️ Reply with the text to send to <b>{handle}</b> instead.",
            reply_markup=cancel_keyboard(approval_id),
        )

    async def ask_to_confirm(self, lead: dict, approval_id: str, text: str) -> int:
        return await self.send(
            confirm_text(lead, text), reply_markup=confirm_keyboard(approval_id)
        )

    async def resolve_card(
        self, message_id: int, lead: dict, approval: dict, outcome: str,
        sent_text: str | None = None,
    ) -> None:
        """Rewrite a handled card in place rather than posting a second message.

        Editing keeps one entry per lead in the chat instead of two, and leaves
        the outcome attached to the message it belongs to.
        """
        try:
            await self._call(
                "editMessageText",
                chat_id=config.TELEGRAM_CHAT_ID,
                message_id=message_id,
                text=resolved_text(lead, approval, outcome, sent_text),
                parse_mode="HTML",
                reply_markup={"inline_keyboard": []},
            )
        except RuntimeError as exc:  # too old to edit, or already edited
            log.info("could not resolve card %s: %s", message_id, exc)
            await self.send(f"{outcome} {html.escape(lead.get('handle') or lead['igsid'])}")

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            await self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except RuntimeError as exc:
            log.info("answerCallbackQuery failed: %s", exc)

    async def aclose(self) -> None:
        await self._client.aclose()
