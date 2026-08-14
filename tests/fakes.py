"""Stand-ins for the two external services, so the flow is testable offline."""
from __future__ import annotations

from app.models import Draft, DraftSet, LeadUpdate


class FakeInstagram:
    def __init__(self, profile: dict | None = None, discovery: dict | None = None):
        self._profile = profile or {}
        self._discovery = discovery or {}
        self.sent: list[tuple[str, str]] = []
        self.fail_send: str | None = None

    async def send_text(self, igsid, text, *, last_inbound_at):
        if self.fail_send:
            raise RuntimeError(self.fail_send)
        self.sent.append((igsid, text))
        return {"message_id": "mid.out"}

    async def profile(self, igsid):
        return self._profile

    async def business_discovery(self, username):
        return self._discovery


class FakeTelegram:
    def __init__(self):
        self.cards: list[tuple[dict, dict]] = []
        self.messages: list[str] = []
        self.cleared: list[tuple[int, str]] = []
        self.answers: list[str] = []
        self._next_id = 100

    async def send_approval(self, lead, approval):
        self.cards.append((lead, approval))
        self._next_id += 1
        return self._next_id

    async def send(self, text, *, force_reply=False):
        self.messages.append(text)
        self._next_id += 1
        return self._next_id

    async def clear_keyboard(self, message_id, footer):
        self.cleared.append((message_id, footer))

    async def answer_callback(self, callback_id, text=""):
        self.answers.append(text)


def draft_set(stage="first_contact", **lead_update) -> DraftSet:
    return DraftSet(
        read="They asked a question.",
        stage=stage,
        drafts=[
            Draft(tone="warm", text="warm draft"),
            Draft(tone="direct", text="direct draft"),
            Draft(tone="low_pressure", text="low pressure draft"),
        ],
        lead_update=LeadUpdate(
            needs=lead_update.get("needs"),
            offered=lead_update.get("offered"),
            price=lead_update.get("price"),
            commitments=lead_update.get("commitments"),
        ),
    )
