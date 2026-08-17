"""The two public doors. Both are authenticated; neither is a place to be sloppy."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def captured(monkeypatch):
    seen = {"incoming": [], "callbacks": [], "messages": []}

    async def incoming(igsid, text, mid):
        seen["incoming"].append((igsid, text, mid))

    async def callback(payload):
        seen["callbacks"].append(payload)

    async def message(payload):
        seen["messages"].append(payload)

    monkeypatch.setattr(main, "_process_incoming", incoming)
    monkeypatch.setattr(main, "_process_callback", callback)
    monkeypatch.setattr(main, "_process_message", message)
    return seen


def signed(body: dict) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    digest = hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


DM = {
    "object": "instagram",
    "entry": [{"messaging": [
        {"sender": {"id": "IG1"}, "message": {"mid": "m1", "text": "hey"}}
    ]}],
}


def test_instagram_verification_echoes_the_challenge(client):
    response = client.get("/webhooks/instagram", params={
        "hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "9001",
    })
    assert response.status_code == 200
    assert response.text == "9001"


def test_instagram_verification_rejects_a_wrong_token(client):
    response = client.get("/webhooks/instagram", params={
        "hub.mode": "subscribe", "hub.verify_token": "guess", "hub.challenge": "9001",
    })
    assert response.status_code == 403


def test_a_signed_delivery_is_queued_for_drafting(client, captured):
    raw, headers = signed(DM)
    assert client.post("/webhooks/instagram", content=raw, headers=headers).status_code == 200
    assert captured["incoming"] == [("IG1", "hey", "m1")]


def test_an_unsigned_delivery_is_refused_and_never_processed(client, captured):
    raw = json.dumps(DM).encode()
    response = client.post("/webhooks/instagram", content=raw,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 403
    assert captured["incoming"] == []


def test_a_delivery_signed_for_different_bytes_is_refused(client, captured):
    _, headers = signed(DM)
    tampered = json.dumps({**DM, "entry": []}).encode()
    assert client.post("/webhooks/instagram", content=tampered,
                       headers=headers).status_code == 403
    assert captured["incoming"] == []


def test_telegram_requires_the_shared_secret(client, captured):
    update = {"callback_query": {"id": "1", "data": "s:abc:0"}}
    assert client.post("/webhooks/telegram", json=update).status_code == 403
    assert client.post("/webhooks/telegram", json=update,
                       headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code == 403
    assert captured["callbacks"] == []


def test_telegram_routes_callbacks_and_messages(client, captured):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "tg-secret"}
    client.post("/webhooks/telegram", json={"callback_query": {"id": "1"}}, headers=headers)
    client.post("/webhooks/telegram", json={"message": {"text": "hi"}}, headers=headers)
    assert len(captured["callbacks"]) == 1
    assert len(captured["messages"]) == 1


def test_approvals_from_another_chat_are_ignored():
    assert main._authorised("4242")
    assert main._authorised(4242)
    assert not main._authorised("9999")


def test_httpx_request_logging_is_silenced_so_credentials_never_reach_the_log():
    # httpx logs the full URL of every request at INFO — Telegram's bot token
    # lives in that URL path, and our own Instagram client's access token is a
    # URL query param. Regression test for the token-leak fix in app/main.py.
    import logging

    assert logging.getLogger("httpx").level >= logging.WARNING
