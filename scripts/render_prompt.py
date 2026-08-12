#!/usr/bin/env python3
"""Fill prompts/dm-reply.md with a lead JSON file.

    python3 scripts/render_prompt.py leads/example-lead.json

Prints the rendered prompt to stdout. Any placeholder missing from the lead file
is filled with "unknown" rather than left as {{...}}, so the model never sees a
literal template token and invent a value for it.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "prompts" / "dm-reply.md"


def render(lead: dict) -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    # Drop the file's own header — everything before the --- rule is documentation.
    text = text.split("\n---\n", 1)[-1].lstrip("\n")
    missing = []

    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in lead:
            missing.append(key)
            return "unknown"
        return str(lead[key])

    out = re.sub(r"\{\{(\w+)\}\}", sub, text)
    if missing:
        print(f"warning: no value for {', '.join(sorted(set(missing)))}", file=sys.stderr)
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    lead = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(render(lead))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
