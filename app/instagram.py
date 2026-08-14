"""Instagram Messaging API: webhook verification, profile lookup, sending."""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.config import config

log = logging.getLogger(__name__)

# Standard messaging window. Past this, a reply needs the HUMAN_AGENT tag (7 days),
# which requires the human_agent permission on the app.
STANDARD_WINDOW_SECONDS = 24 * 60 * 60
HUMAN_AGENT_WINDOW_SECONDS = 7 * 24 * 60 * 60


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Check X-Hub-Signature-256 against the app secret over the raw request body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        config.ig_app_secret().encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def verify_challenge(params: dict[str, str]) -> str | None:
    """Meta's GET handshake. Returns the challenge to echo, or None to reject."""
    if params.get("hub.mode") == "subscribe" and params.get(
        "hub.verify_token"
    ) == config.ig_verify_token():
        return params.get("hub.challenge")
    return None


def parse_events(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Pull inbound text messages out of a webhook payload.

    Skips echoes (our own sends come back through the same webhook), reactions,
    read receipts, deletions, and attachment-only messages — an attachment with no
    text yields no draftable content, so it is recorded upstream but not drafted on.
    """
    events: list[dict[str, str]] = []
    if payload.get("object") != "instagram":
        return events
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo") or message.get("is_deleted"):
                continue
            text = (message.get("text") or "").strip()
            sender = (event.get("sender") or {}).get("id")
            if not text or not sender:
                continue
            events.append({"igsid": sender, "text": text, "mid": message.get("mid", "")})
    return events


class InstagramClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=20)

    def _url(self, node: str) -> str:
        return f"{config.IG_BASE_URL}/{config.IG_API_VERSION}/{node}"

    async def send_text(self, igsid: str, text: str, *, last_inbound_at: float | None) -> dict:
        """Send a DM. Raises RuntimeError if the messaging window has closed."""
        age = time.time() - last_inbound_at if last_inbound_at else None
        body: dict[str, Any] = {
            "recipient": {"id": igsid},
            "message": {"text": text},
        }
        if age is not None and age > STANDARD_WINDOW_SECONDS:
            if not config.IG_USE_HUMAN_AGENT_TAG:
                raise RuntimeError(
                    f"24h messaging window closed ({age / 3600:.1f}h since their last "
                    "message). Set IG_USE_HUMAN_AGENT_TAG=1 once the human_agent "
                    "permission is approved for your app, or reply in the Instagram app."
                )
            if age > HUMAN_AGENT_WINDOW_SECONDS:
                raise RuntimeError(
                    f"7-day human-agent window closed ({age / 86400:.1f} days). "
                    "This thread can only be answered in the Instagram app."
                )
            body["messaging_type"] = "MESSAGE_TAG"
            body["tag"] = "HUMAN_AGENT"

        response = await self._client.post(
            self._url(f"{config.IG_SEND_NODE}/messages"),
            params={"access_token": config.ig_token()},
            json=body,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Instagram send failed ({response.status_code}): {response.text}")
        return response.json()

    async def profile(self, igsid: str) -> dict[str, Any]:
        """Messaging profile for a sender. Note: this endpoint does NOT return a bio."""
        fields = "name,username,follower_count,is_user_follow_business,is_business_follow_user"
        response = await self._client.get(
            self._url(igsid), params={"fields": fields, "access_token": config.ig_token()}
        )
        if response.status_code >= 400:
            log.warning("profile lookup failed for %s: %s", igsid, response.text)
            return {}
        return response.json()

    async def business_discovery(self, username: str) -> dict[str, Any]:
        """Bio and recent captions for a professional account.

        Optional and best-effort: needs a Facebook Login token with instagram_basic
        (IG_DISCOVERY_TOKEN + IG_USER_ID), and returns nothing for personal accounts.
        """
        if not (config.IG_DISCOVERY_TOKEN and config.IG_USER_ID and username):
            return {}
        query = (
            f"business_discovery.username({username})"
            "{biography,followers_count,media.limit(6){caption}}"
        )
        response = await self._client.get(
            f"{config.FB_GRAPH_URL}/{config.IG_API_VERSION}/{config.IG_USER_ID}",
            params={"fields": query, "access_token": config.IG_DISCOVERY_TOKEN},
        )
        if response.status_code >= 400:
            log.info("business_discovery unavailable for %s: %s", username, response.text)
            return {}
        return response.json().get("business_discovery", {})

    async def aclose(self) -> None:
        await self._client.aclose()
