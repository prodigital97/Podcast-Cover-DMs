#!/usr/bin/env python3
"""Check every example in examples/ against the hard rules in the prompt.

    python3 scripts/check_examples.py

Catches the failures that are actually checkable in code: missing fields, unknown
stages, drafts over the word limit, emoji used first by us, hashtags, and pitch
language in a soft_no / hard_no reply. Tone and specificity still need a human.
"""
import glob
import json
import pathlib
import re
import sys

STAGES = {"first_contact", "building", "green_light", "soft_no", "hard_no", "active_client"}
TONES = ["warm", "direct", "low_pressure"]
LEAD_FIELDS = json.loads((pathlib.Path(__file__).resolve().parent.parent / "leads" / "_schema.json").read_text()).keys()
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U0001F1E6-\U0001F1FF]")
# Words that mean we are still selling after being told no.
PITCHY = re.compile(r"\b(discount|package|rate|per month|retainer|portfolio|book a call|would you be open)\b", re.I)


def check(path: str) -> list[str]:
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    lead, out = doc["lead"], doc["output"]
    errs = []

    for field in LEAD_FIELDS:
        if field not in lead:
            errs.append(f"lead missing {field}")

    stage = out.get("stage")
    if stage not in STAGES:
        errs.append(f"unknown stage {stage!r}")
    if lead.get("status") != stage:
        errs.append(f"stage {stage!r} disagrees with lead status {lead.get('status')!r}")

    if [d["tone"] for d in out["drafts"]] != TONES:
        errs.append("drafts must be warm, direct, low_pressure in that order")

    they_used_emoji = bool(EMOJI.search(lead["full_thread"] + lead["incoming_message"]))
    for d in out["drafts"]:
        text, tone = d["text"], d["tone"]
        words = len(text.split())
        if words >= 60:
            errs.append(f"{tone}: {words} words, limit is 60")
        if "#" in text:
            errs.append(f"{tone}: hashtag")
        if EMOJI.search(text) and not they_used_emoji:
            errs.append(f"{tone}: emoji, but they never used one")
        if stage in {"soft_no", "hard_no"} and PITCHY.search(text):
            errs.append(f"{tone}: still pitching after a no — {PITCHY.search(text).group(0)!r}")

    return errs


def main() -> int:
    failed = False
    for path in sorted(glob.glob("examples/*.json")):
        errs = check(path)
        if errs:
            failed = True
            print(f"FAIL {path}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"ok   {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
