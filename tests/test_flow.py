"""The path a real DM takes: webhook -> drafts -> approval -> Instagram."""
import asyncio
import time

import pytest

from app import approvals, db
from tests.fakes import FakeInstagram, FakeTelegram, draft_set


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def stub_draft(monkeypatch):
    calls = []

    async def fake_draft(lead, incoming, thread, *, nudge=""):
        calls.append({"lead": lead, "incoming": incoming, "thread": thread, "nudge": nudge})
        return draft_set(stage="green_light", needs="wants clips")

    monkeypatch.setattr(approvals, "draft", fake_draft)
    return calls


def test_incoming_dm_builds_a_lead_and_posts_one_card(stub_draft):
    instagram = FakeInstagram(
        profile={"username": "coldcasecounty", "name": "Cold Case County", "follower_count": 18000},
        discovery={"biography": "unsolved cases from the Rust Belt", "media": {
            "data": [{"caption": "new episode on the 1994 case"}]}},
    )
    telegram = FakeTelegram()

    run(approvals.handle_incoming("IG1", "what do you charge", "m1", instagram, telegram))

    lead = db.get_lead("IG1")
    assert lead["handle"] == "@coldcasecounty"
    assert lead["audience_size"] == "18000"
    assert lead["bio"] == "unsolved cases from the Rust Belt"
    assert "1994 case" in lead["about"]
    assert len(telegram.cards) == 1
    assert telegram.cards[0][1]["stage"] == "green_light"


def test_lead_update_and_stage_are_folded_back_into_the_lead(stub_draft):
    run(approvals.handle_incoming("IG1", "what do you charge", "m1", FakeInstagram(), FakeTelegram()))
    lead = db.get_lead("IG1")
    assert lead["status"] == "green_light"
    assert lead["needs"] == "wants clips"
    # Nulls in lead_update mean unchanged, so the defaults survive.
    assert lead["price"] == "not discussed"


def test_a_replayed_webhook_delivery_does_not_draft_twice(stub_draft):
    telegram = FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", FakeInstagram(), telegram))
    run(approvals.handle_incoming("IG1", "hey", "m1", FakeInstagram(), telegram))
    assert len(telegram.cards) == 1
    assert len(stub_draft) == 1


def test_the_thread_passed_to_the_drafter_is_oldest_first(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "first", "m1", instagram, telegram))
    approval_id = db.open_approval_for("IG1")["id"]
    run(approvals.send_approved(approval_id, "our reply", instagram, telegram))
    run(approvals.handle_incoming("IG1", "second", "m2", instagram, telegram))

    assert stub_draft[-1]["thread"] == "them: first\npronoy: our reply\nthem: second"


def test_approving_a_draft_sends_it_and_closes_the_card(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")

    run(approvals.send_approved(approval["id"], approval["drafts"][1]["text"], instagram, telegram))

    assert instagram.sent == [("IG1", "direct draft")]
    assert db.get_approval(approval["id"])["state"] == "sent"
    assert db.thread("IG1").endswith("pronoy: direct draft")
    assert telegram.resolved[0]["outcome"] == "✅ Sent to"
    # The resolved card shows what actually went out, not just that something did.
    assert telegram.resolved[0]["sent_text"] == "direct draft"


def test_a_sent_approval_cannot_be_sent_again(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")
    run(approvals.send_approved(approval["id"], "once", instagram, telegram))

    with pytest.raises(RuntimeError, match="already sent"):
        run(approvals.send_approved(approval["id"], "twice", instagram, telegram))
    assert len(instagram.sent) == 1


def test_a_failed_instagram_send_leaves_nothing_recorded(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    instagram.fail_send = "24h messaging window closed"
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")

    with pytest.raises(RuntimeError, match="window closed"):
        run(approvals.send_approved(approval["id"], "too late", instagram, telegram))

    assert db.get_approval(approval["id"])["state"] == "open"
    assert "pronoy:" not in db.thread("IG1")


def test_redraft_supersedes_the_old_card_and_asks_for_a_new_angle(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    first = db.open_approval_for("IG1")

    run(approvals.redraft(first["id"], instagram, telegram))

    assert db.get_approval(first["id"])["state"] == "superseded"
    assert len(telegram.cards) == 2
    assert "different angle" in stub_draft[-1]["nudge"]
    assert db.open_approval_for("IG1")["id"] != first["id"]


def test_enrichment_runs_once_per_lead(stub_draft):
    instagram, telegram = FakeInstagram(profile={"username": "x"}), FakeTelegram()
    run(approvals.handle_incoming("IG1", "one", "m1", instagram, telegram))
    db.upsert_lead("IG1", handle="@edited-by-hand")
    run(approvals.handle_incoming("IG1", "two", "m2", instagram, telegram))
    assert db.get_lead("IG1")["handle"] == "@edited-by-hand"


def test_voice_notes_are_inferred_from_how_they_actually_type(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming(
        "IG1", "yeah mate sounds good, send it over whenever you get a chance", "m1",
        instagram, telegram,
    ))
    assert "lowercase" in db.get_lead("IG1")["voice_notes"]
    assert "no emoji" in db.get_lead("IG1")["voice_notes"]


# --- edited replies must be confirmed, never fired off a bare typed line ----

def test_a_typed_edit_is_staged_for_confirmation_not_sent(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")
    db.set_approval_state(approval["id"], "awaiting_edit")

    run(approvals.stage_edit(approval["id"], "my own words", telegram))

    assert instagram.sent == []                                    # nothing sent yet
    assert telegram.confirms[0][2] == "my own words"               # shown back for review
    assert db.get_approval(approval["id"])["state"] == "awaiting_confirm"


def test_confirming_a_staged_edit_sends_exactly_that_text(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")
    db.set_approval_state(approval["id"], "awaiting_edit")
    run(approvals.stage_edit(approval["id"], "my own words", telegram))

    staged = db.get_approval(approval["id"])["sent_text"]
    run(approvals.send_approved(approval["id"], staged, instagram, telegram))

    assert instagram.sent == [("IG1", "my own words")]
    assert db.thread("IG1").endswith("pronoy: my own words")


def test_cancelling_an_edit_reopens_the_card_so_later_typing_is_inert(stub_draft):
    # The hazard this closes: tap Edit, get distracted, then type anything at
    # all in the bot chat hours later — it used to go straight to the lead.
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    approval = db.open_approval_for("IG1")
    db.set_approval_state(approval["id"], "awaiting_edit")

    run(approvals.cancel_edit(approval["id"], telegram))

    assert db.get_approval(approval["id"])["state"] == "open"
    assert db.awaiting_edit() is None          # nothing will swallow the next message
    assert instagram.sent == []


def test_the_card_is_given_the_context_it_needs_to_render(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    context = telegram.card_context[0]
    assert context["inbound_count"] == 1
    assert context["last_inbound_at"] is not None


def test_redraft_resolves_the_old_card_in_place(stub_draft):
    instagram, telegram = FakeInstagram(), FakeTelegram()
    run(approvals.handle_incoming("IG1", "hey", "m1", instagram, telegram))
    first = db.open_approval_for("IG1")
    run(approvals.redraft(first["id"], instagram, telegram))
    assert telegram.resolved[0]["outcome"].endswith("Redrafted —")
    assert telegram.resolved[0]["sent_text"] is None
