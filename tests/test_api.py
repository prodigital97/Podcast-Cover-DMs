"""Tests for the Lead CRM and Copilot REST API."""
import pytest
from fastapi.testclient import TestClient

from app import db, main
from tests.fakes import FakeInstagram, FakeTelegram, draft_set


@pytest.fixture
def client(monkeypatch):
    async def fake_draft(lead, incoming, thread, *, nudge=""):
        return draft_set(stage="green_light", needs="wants rebrand")

    monkeypatch.setattr(main, "draft", fake_draft)
    with TestClient(main.app) as test_client:
        test_client.auth = ("test-admin", "test-password")
        yield test_client


def test_api_requires_auth():
    with TestClient(main.app) as anon_client:
        assert anon_client.get("/api/leads").status_code == 401
        assert anon_client.get("/dashboard").status_code == 401


def test_lead_crud_and_message_flow(client):
    # 1. Create a new lead
    create_res = client.post(
        "/api/leads",
        json={
            "handle": "founderpodcast",
            "podcast_name": "Founder Stories",
            "audience_size": "25000",
            "bio": "Weekly tech podcast interviews",
            "notes": "Interested in £300 rebrand",
            "initial_message": "Hey Pronoy! What do you charge for a full cover rebrand?",
        },
    )
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["success"] is True
    igsid = data["igsid"]
    assert data["lead"]["handle"] == "@founderpodcast"
    assert data["drafts"] is not None
    assert len(data["drafts"]["drafts"]) == 3

    # 2. List leads
    list_res = client.get("/api/leads")
    assert list_res.status_code == 200
    leads = list_res.json()["leads"]
    assert any(l["igsid"] == igsid for l in leads)

    # 3. Get single lead details
    get_res = client.get(f"/api/leads/{igsid}")
    assert get_res.status_code == 200
    lead_detail = get_res.json()
    assert len(lead_detail["messages"]) == 1
    assert lead_detail["messages"][0]["text"] == "Hey Pronoy! What do you charge for a full cover rebrand?"

    # 4. Add outbound message (Pronoy replies)
    msg_res = client.post(
        f"/api/leads/{igsid}/messages",
        json={"direction": "pronoy", "text": "Hey! Rebrands usually start around £250. Got a link to your show?"},
    )
    assert msg_res.status_code == 200
    assert len(msg_res.json()["messages"]) == 2

    # 5. Export CSV
    csv_res = client.get("/api/export/csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "@founderpodcast" in csv_res.text
    assert "Founder Stories" in csv_res.text

    # 6. Delete lead
    del_res = client.delete(f"/api/leads/{igsid}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
