from app.telegram import approval_keyboard, approval_text, parse_callback


def test_parse_callback_roundtrip_and_rejection():
    assert parse_callback("s:abc123:2") == ("s", "abc123", 2)
    assert parse_callback("bogus") is None
    assert parse_callback("z:abc123:0") is None
    assert parse_callback("s:abc123:x") is None


DRAFTS = [{"tone": "warm", "text": "a"}, {"tone": "direct", "text": "b"},
          {"tone": "low_pressure", "text": "c"}]


def test_callback_data_fits_telegrams_64_byte_budget():
    keyboard = approval_keyboard("a" * 12, DRAFTS)
    for row in keyboard["inline_keyboard"]:
        for button in row:
            assert len(button["callback_data"].encode()) <= 64


def test_send_row_matches_the_number_of_drafts():
    assert len(approval_keyboard("id", DRAFTS[:2])["inline_keyboard"][0]) == 2


def test_send_buttons_name_the_tone_so_you_need_not_scroll_back_up():
    row = approval_keyboard("id", DRAFTS)["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["1 · Warm", "2 · Direct", "3 · Low-key"]


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


# --- card readability ------------------------------------------------------

def test_audience_and_stage_are_humanised_not_raw_data():
    from app.telegram import humanise_audience
    assert humanise_audience("18000") == "18k"
    assert humanise_audience("1500000") == "1.5m"
    assert humanise_audience("840") == "840"
    assert humanise_audience(None) is None
    assert humanise_audience("lots") == "lots"  # non-numeric passes through


def test_the_card_spells_out_the_stage():
    lead = {"igsid": "IG1", "handle": "@x", "audience_size": "18000"}
    approval = {"id": "a", "stage": "green_light", "incoming_text": "hi", "read": "r",
                "drafts": [{"tone": "warm", "text": "t"}]}
    text = approval_text(lead, approval)
    assert "Green light" in text and "green_light" not in text
    assert "18k" in text and "18000" not in text


def test_the_card_shows_how_long_is_left_to_reply():
    import time
    from app.telegram import window_note
    now = time.time()
    assert "23h left" in window_note(now - 3600, now=now)
    assert window_note(now - 23.5 * 3600, now=now).startswith("⚠️")   # under an hour
    assert "closed" in window_note(now - 25 * 3600, now=now)
    assert window_note(None) is None


def test_the_card_says_where_in_the_conversation_this_is():
    lead = {"igsid": "IG1", "handle": "@x"}
    approval = {"id": "a", "stage": "building", "incoming_text": "hi", "read": "r",
                "drafts": [{"tone": "warm", "text": "t"}]}
    assert "their first message" in approval_text(lead, approval, inbound_count=1)
    assert "their 6th message" in approval_text(lead, approval, inbound_count=6)


def test_word_counts_are_shown_so_length_matching_is_checkable():
    # Rule 7 is "match their length" — the reviewer can't judge that by eye.
    lead = {"igsid": "IG1", "handle": "@x"}
    approval = {"id": "a", "stage": "building", "incoming_text": "one two three",
                "read": "r", "drafts": [{"tone": "warm", "text": "a b c d"}]}
    text = approval_text(lead, approval)
    assert "3 words" in text and "4 words" in text


def test_a_resolved_card_drops_the_drafts_and_shows_what_was_sent():
    from app.telegram import resolved_text
    lead = {"igsid": "IG1", "handle": "@x"}
    approval = {"incoming_text": "what do you charge",
                "drafts": [{"tone": "warm", "text": "rejected draft"}]}
    text = resolved_text(lead, approval, "✅ Sent to", "the one I picked")
    assert "the one I picked" in text
    assert "rejected draft" not in text          # noise once decided
    assert "what do you charge" in text          # but their message stays


def test_resolved_and_confirm_cards_escape_html():
    from app.telegram import confirm_text, resolved_text
    lead = {"igsid": "IG1", "handle": "@x"}
    approval = {"incoming_text": "<b>hi</b>", "drafts": []}
    assert "<b>hi</b>" not in resolved_text(lead, approval, "✅ Sent to", "<script>x</script>")
    assert "<script>" not in confirm_text(lead, "<script>x</script>")
