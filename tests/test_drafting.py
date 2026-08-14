from pydantic import TypeAdapter

from app.drafting import infer_voice_notes
from app.models import DraftSet
from app.prompt import render


# Structured outputs support a subset of JSON Schema. These are the keywords that
# get silently dropped or rejected, so a model field that generates one is a bug.
UNSUPPORTED = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems",
}


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_the_response_schema_uses_only_supported_keywords():
    for node in _walk(TypeAdapter(DraftSet).json_schema()):
        assert not (UNSUPPORTED & node.keys()), f"unsupported constraint in {node}"


def test_every_object_in_the_schema_is_closed_and_fully_required():
    schema = TypeAdapter(DraftSet).json_schema()
    for node in _walk(schema):
        if node.get("type") == "object" and "properties" in node:
            assert set(node.get("required", [])) == set(node["properties"]), node


def test_voice_notes_read_lowercase_and_emoji_use():
    notes = infer_voice_notes(["yeah we know 😅 it's been on the list", "lol yeah"])
    assert "lowercase" in notes and "uses emoji" in notes and "one-liners" in notes


def test_voice_notes_read_formal_writing():
    notes = infer_voice_notes([
        "Thank you for reaching out. We are a commercial mechanical contractor and "
        "the podcast is aimed squarely at recruitment, which has been our constraint "
        "for the last two intakes across both branches of the business.",
    ])
    assert "lowercase" not in notes
    assert "full paragraphs" in notes


def test_voice_notes_are_unknown_with_nothing_to_go_on():
    assert infer_voice_notes([]) == "unknown"


def test_rendering_reports_missing_fields_and_never_leaks_a_placeholder():
    prompt, missing = render({"handle": "@x", "incoming_message": "hi", "full_thread": ""})
    assert "{{" not in prompt
    assert "bio" in missing
    assert "unknown" in prompt


def test_the_prompt_carries_the_lead_update_extension():
    prompt, _ = render({"handle": "@x"})
    assert "lead_update" in prompt


def test_voice_notes_stay_quiet_about_case_on_too_little_text():
    # One short message is not evidence of a lowercase habit.
    assert "lowercase" not in infer_voice_notes(["ok sounds good"])
