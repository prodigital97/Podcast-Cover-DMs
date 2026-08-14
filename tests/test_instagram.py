import hashlib
import hmac

from app.instagram import parse_events, verify_challenge, verify_signature


def sign(body: bytes, secret: str = "app-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_accepts_matching_digest():
    body = b'{"object":"instagram"}'
    assert verify_signature(body, sign(body))


def test_signature_rejects_tampered_body_and_missing_header():
    body = b'{"object":"instagram"}'
    assert not verify_signature(b'{"object":"evil"}', sign(body))
    assert not verify_signature(body, None)
    assert not verify_signature(body, "sha1=abc")


def test_challenge_requires_the_right_verify_token():
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"}
    assert verify_challenge(params) == "42"
    assert verify_challenge({**params, "hub.verify_token": "wrong"}) is None
    assert verify_challenge({**params, "hub.mode": "unsubscribe"}) is None


def _payload(*messages):
    return {
        "object": "instagram",
        "entry": [{"id": "ig-account", "messaging": [
            {"sender": {"id": "IGSID1"}, "recipient": {"id": "ig-account"}, "message": m}
            for m in messages
        ]}],
    }


def test_parse_events_extracts_inbound_text():
    events = parse_events(_payload({"mid": "m1", "text": "  hey  "}))
    assert events == [{"igsid": "IGSID1", "text": "hey", "mid": "m1"}]


def test_parse_events_skips_echoes_deletions_and_attachment_only():
    payload = _payload(
        {"mid": "m1", "text": "our own reply", "is_echo": True},
        {"mid": "m2", "text": "gone", "is_deleted": True},
        {"mid": "m3", "attachments": [{"type": "image"}]},
        {"mid": "m4", "text": "   "},
    )
    assert parse_events(payload) == []


def test_parse_events_ignores_other_objects():
    assert parse_events({"object": "page", "entry": [{"messaging": [{"message": {"text": "x"}}]}]}) == []
