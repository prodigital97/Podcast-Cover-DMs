"""Render prompts/dm-reply.md from a lead dict.

Shared by the CLI (scripts/render_prompt.py) and the live drafter (app/drafting.py)
so there is exactly one copy of the prompt-filling rules.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "prompts" / "dm-reply.md"

# The drafter also maintains the pipeline fields, so Pronoy never hand-edits a lead.
# Appended to the base prompt rather than living in it, because the base prompt is the
# spec for the drafts themselves.
LEAD_UPDATE_EXTENSION = """

## ALSO RETURN: lead_update

Alongside the drafts, return a `lead_update` object recording anything their new
message changed about the pipeline. Use null for a field the message didn't touch —
never restate an unchanged value, and never invent one.

  needs        — what they've now said they need, if this message added to it
  offered      — what Pronoy has offered, if this message is a response to an offer
  price        — a number if they named one, otherwise null
  commitments  — anything Pronoy now owes them (a sample promised, a file to send)

{
  "read": "...",
  "stage": "...",
  "drafts": [...],
  "lead_update": {"needs": null, "offered": null, "price": null, "commitments": null}
}
"""


def render(lead: dict, *, extension: str = LEAD_UPDATE_EXTENSION) -> tuple[str, list[str]]:
    """Return (prompt, missing_fields). Missing placeholders render as "unknown"."""
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.split("\n---\n", 1)[-1].lstrip("\n")
    missing: list[str] = []

    def sub(match: re.Match) -> str:
        key = match.group(1)
        value = lead.get(key)
        if value in (None, ""):
            missing.append(key)
            return "unknown"
        return str(value)

    return re.sub(r"\{\{(\w+)\}\}", sub, text) + extension, sorted(set(missing))
