from app.telegram import approval_keyboard, approval_text, parse_callback


def test_parse_callback_roundtrip_and_rejection():
    assert parse_callback("s:abc123:2") == ("s", "abc123", 2)
    assert parse_callback("bogus") is None
    assert parse_callback("z:abc123:0") is None
    assert parse_callback("s:abc123:x") is None


def test_callback_data_fits_telegrams_64_byte_budget():
    keyboard = approval_keyboard("a" * 12, 3)
    for row in keyboard["inline_keyboard"]:
        for button in row:
            assert len(button["callback_data"].encode()) <= 64


def test_send_row_matches_the_number_of_drafts():
    assert len(approval_keyboard("id", 2)["inline_keyboard"][0]) == 2


def test_card_escapes_html_from_the_lead_and_their_message():
    lead = {"igsid": "IG1", "handle": "@a<b>", "audience_size": "18k"}
    approval = {
        "id": "x", "stage": "building", "incoming_text": "<script>alert(1)</script>",
        "read": "fine & good", "drafts": [{"tone": "warm", "text": "5 > 3"}],
    }
    text = approval_text(lead, approval)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "fine &amp; good" in text
    assert "5 &gt; 3" in text
    assert "@a&lt;b&gt;" in text


def test_card_falls_back_to_the_igsid_when_the_handle_is_unknown():
    lead = {"igsid": "IG1", "handle": None, "audience_size": None}
    approval = {"id": "x", "stage": "first_contact", "incoming_text": "hi",
                "read": "r", "drafts": [{"tone": "warm", "text": "t"}]}
    assert "IG1" in approval_text(lead, approval)
