"""Turn a lead plus their new message into three drafts."""
from __future__ import annotations

import logging
import re

import anthropic

from app.config import config
from app.models import DraftSet
from app.prompt import render

log = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U0001F1E6-\U0001F1FF]"
)


def infer_voice_notes(messages: list[str]) -> str:
    """Describe how they type, from how they've actually typed.

    Cheap and deterministic on purpose — this field exists so the drafter matches
    their register, and guessing it from a couple of messages beats leaving it unknown.
    """
    if not messages:
        return "unknown"
    joined = " ".join(messages)
    letters = [c for c in joined if c.isalpha()]
    notes = []
    # Ordinary prose is ~95% lowercase letters, so a ratio threshold flags everyone.
    # The real signal is the near-total absence of capitals across enough text.
    uppercase = sum(c.isupper() for c in letters)
    if len(letters) >= 25 and uppercase / len(letters) < 0.01:
        notes.append("writes in lowercase")
    if EMOJI.search(joined):
        notes.append("uses emoji")
    else:
        notes.append("no emoji")
    average = sum(len(m.split()) for m in messages) / len(messages)
    notes.append("one-liners" if average < 12 else "writes in full paragraphs")
    if any(len(m) > 400 for m in messages):
        notes.append("sends long messages")
    return ", ".join(notes)


async def draft(lead: dict, incoming: str, thread: str, *, nudge: str = "") -> DraftSet:
    """Ask the model for the three drafts. Raises on refusal or a failed parse."""
    lead_view = {
        "handle": lead.get("handle"),
        "podcast_name": lead.get("podcast_name"),
        "bio": lead.get("bio"),
        "about": lead.get("about"),
        "audience_size": lead.get("audience_size"),
        "voice_notes": lead.get("voice_notes"),
        "status": lead.get("status"),
        "needs": lead.get("needs"),
        "offered": lead.get("offered"),
        "price": lead.get("price"),
        "commitments": lead.get("commitments"),
        "full_thread": thread,
        "incoming_message": incoming,
    }
    prompt, missing = render(lead_view)
    if missing:
        log.info("drafting %s with unknown: %s", lead.get("igsid"), ", ".join(missing))
    if nudge:
        prompt += f"\n\n## THIS ROUND\n{nudge}\n"

    response = await client().messages.parse(
        model=config.MODEL,
        max_tokens=8000,
        output_config={"effort": config.EFFORT},
        messages=[{"role": "user", "content": prompt}],
        output_format=DraftSet,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model declined to draft: {response.stop_details}")
    if response.parsed_output is None:
        raise RuntimeError(f"drafting returned no parseable output (stop: {response.stop_reason})")
    return response.parsed_output


REDRAFT_NUDGE = (
    "The previous three drafts were rejected. Take a visibly different angle — a "
    "different opening, a different specific detail from their world, a different "
    "question. Do not rephrase the earlier attempt."
)
