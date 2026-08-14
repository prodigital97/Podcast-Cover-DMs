"""Telegram bot: the approval surface."""
from __future__ import annotations

import html
import logging
from typing import Any

import httpx

from app.config import config

log = logging.getLogger(__name__)

TONE_LABELS = {"warm": "Warm", "direct": "Direct", "low_pressure": "Low pressure"}
NUMERALS = ["1️⃣", "2️⃣", "3️⃣"]


def approval_text(lead: dict[str, Any], approval: dict[str, Any]) -> str:
    """The card body. HTML parse mode — every interpolated value is escaped."""
    handle = html.escape(lead.get("handle") or lead["igsid"])
    audience = lead.get("audience_size")
    who = f"<b>{handle}</b>" + (f" · {html.escape(str(audience))}" if audience else "")
    lines = [
        f"\U0001f4e9 {who} · <i>{html.escape(approval['stage'])}</i>",
        "",
        f"<blockquote>{html.escape(approval['incoming_text'])}</blockquote>",
        "",
        f"<i>{html.escape(approval['read'])}</i>",
        "",
    ]
    for index, draft in enumerate(approval["drafts"][:3]):
        label = TONE_LABELS.get(draft["tone"], draft["tone"])
        lines.append(f"{NUMERALS[index]} <b>{label}</b>\n{html.escape(draft['text'])}\n")
    return "\n".join(lines).strip()


def approval_keyboard(approval_id: str, draft_count: int) -> dict[str, Any]:
    send_row = [
        {"text": f"Send {i + 1}", "callback_data": f"s:{approval_id}:{i}"}
        for i in range(min(draft_count, 3))
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


def parse_callback(data: str) -> tuple[str, str, int] | None:
    """"s:<approval_id>:<index>" -> ("s", approval_id, index). 64-byte budget."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in {"s", "e", "r", "x"}:
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

    async def send_approval(self, lead: dict, approval: dict) -> int:
        result = await self._call(
            "sendMessage",
            chat_id=config.TELEGRAM_CHAT_ID,
            text=approval_text(lead, approval),
            parse_mode="HTML",
            reply_markup=approval_keyboard(approval["id"], len(approval["drafts"])),
        )
        return int(result["message_id"])

    async def send(self, text: str, *, force_reply: bool = False) -> int:
        payload: dict[str, Any] = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        if force_reply:
            payload["reply_markup"] = {"force_reply": True, "selective": True}
        result = await self._call("sendMessage", **payload)
        return int(result["message_id"])

    async def clear_keyboard(self, message_id: int, footer: str) -> None:
        """Strip the buttons off a resolved card and append its outcome."""
        try:
            await self._call(
                "editMessageReplyMarkup",
                chat_id=config.TELEGRAM_CHAT_ID,
                message_id=message_id,
                reply_markup={"inline_keyboard": []},
            )
        except RuntimeError as exc:  # already edited, or message too old
            log.info("could not clear keyboard on %s: %s", message_id, exc)
        await self.send(footer)

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            await self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except RuntimeError as exc:
            log.info("answerCallbackQuery failed: %s", exc)

    async def aclose(self) -> None:
        await self._client.aclose()
