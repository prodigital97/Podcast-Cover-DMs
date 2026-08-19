"""Response schema for the drafter. Enforced by structured outputs, not by parsing."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Stage = Literal[
    "first_contact", "building", "green_light", "soft_no", "hard_no", "active_client"
]
Tone = Literal["warm", "direct", "low_pressure"]


class Draft(BaseModel):
    tone: Tone
    text: str


class LeadUpdate(BaseModel):
    """Anything the new message changed. null means "unchanged" — never a restatement."""

    needs: str | None
    offered: str | None
    price: str | None
    commitments: str | None


class DraftSet(BaseModel):
    read: str
    stage: Stage
    conversion_probability: int
    conversion_rationale: str
    buying_signals: list[str]
    recommended_action: str
    drafts: list[Draft]
    lead_update: LeadUpdate
