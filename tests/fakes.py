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
        self.card_context: list[dict] = []
        self.edit_prompts: list[tuple[dict, str]] = []
        self.confirms: list[tuple[dict, str, str]] = []
        self.resolved: list[dict] = []
        self.messages: list[str] = []
        self.cleared: list[tuple[int, str]] = []
        self.answers: list[str] = []
        self._next_id = 100

    async def send_approval(self, lead, approval, *, last_inbound_at=None, inbound_count=None):
        self.cards.append((lead, approval))
        self.card_context.append({"last_inbound_at": last_inbound_at,
                                  "inbound_count": inbound_count})
        self._next_id += 1
        return self._next_id

    async def send(self, text, *, reply_markup=None):
        self.messages.append(text)
        self._next_id += 1
        return self._next_id

    async def ask_for_edit(self, lead, approval_id):
        self.edit_prompts.append((lead, approval_id))
        self._next_id += 1
        return self._next_id

    async def ask_to_confirm(self, lead, approval_id, text):
        self.confirms.append((lead, approval_id, text))
        self._next_id += 1
        return self._next_id

    async def resolve_card(self, message_id, lead, approval, outcome, sent_text=None):
        self.cleared.append((message_id, outcome))
        self.resolved.append({"message_id": message_id, "outcome": outcome,
                              "sent_text": sent_text})

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
