#!/usr/bin/env python3
"""Validate the employee files before Claude Code loads them.

    python3 check_agents.py

Catches the failures that silently stop an agent from being hired: missing or
malformed frontmatter, a name that does not match its filename, a duplicate
name, or an empty body.
"""
import pathlib
import re
import sys

REQUIRED = {"name", "description"}


def check(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return ["no YAML frontmatter — the file must start with a --- line"]

    errors = []
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            errors.append(f"frontmatter line is not key: value — {line!r}")
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    for field in sorted(REQUIRED - fields.keys()):
        errors.append(f"missing required field: {field}")
    if fields.get("name") and fields["name"] != path.stem:
        errors.append(f"name {fields['name']!r} does not match filename {path.stem!r}")
    if not text[match.end():].strip():
        errors.append("empty body — the agent would have no instructions")
    return errors


def main() -> int:
    paths = sorted((pathlib.Path(__file__).parent / "agents").glob("*.md"))
    if not paths:
        print("no agent files found", file=sys.stderr)
        return 1

    failed = False
    seen: dict[str, str] = {}
    for path in paths:
        errors = check(path)
        name = path.stem
        if name in seen:
            errors.append(f"duplicate agent name, also defined in {seen[name]}")
        seen[name] = path.name
        if errors:
            failed = True
            print(f"FAIL {path.name}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"ok   {path.name}")
    print(f"\n{len(paths)} employees checked")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
