#!/usr/bin/env python3
"""Fill prompts/dm-reply.md with a lead JSON file.

    python3 scripts/render_prompt.py leads/example-lead.json

Prints the rendered prompt to stdout. Any placeholder missing from the lead file is
filled with "unknown" rather than left as {{...}}, so the model never sees a literal
template token and invent a value for it.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.prompt import render  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    lead = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    prompt, missing = render(lead, extension="")
    if missing:
        print(f"warning: no value for {', '.join(missing)}", file=sys.stderr)
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
