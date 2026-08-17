"""Shared by the deploy scripts: find and parse the KEY=value credentials file.

Not part of the app itself — app/config.py reads real process environment
variables, which is correct there because systemd's EnvironmentFile= injects
them for the running service. These are standalone scripts run interactively
by a human, with nothing injecting anything, so they read the file directly.

Two locations, checked in order: local dev keeps .env at the project root;
deploy/setup.sh keeps /etc/podcast-cover-dms/env instead, deliberately outside
the git-managed directory so a redeploy can never overwrite it.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATE_PATHS = [ROOT / ".env", pathlib.Path("/etc/podcast-cover-dms/env")]


def resolve_path(argv: list[str]) -> pathlib.Path:
    """argv[1], if given, overrides auto-detection. Exits with a clear message
    if nothing is found — never returns a path that doesn't exist."""
    if len(argv) > 1:
        path = pathlib.Path(argv[1])
        if not path.exists():
            print(f"no such file: {path}", file=sys.stderr)
            raise SystemExit(2)
        return path
    for path in CANDIDATE_PATHS:
        if path.exists():
            return path
    tried = ", ".join(str(p) for p in CANDIDATE_PATHS)
    print(f"no env file found — tried: {tried}", file=sys.stderr)
    print("copy .env.example to .env (local) or check the deploy setup (server)", file=sys.stderr)
    raise SystemExit(2)


def read(path: pathlib.Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_value(path: pathlib.Path, key: str, value: str) -> None:
    text = path.read_text()
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    text = pattern.sub(f"{key}={value}", text) if pattern.search(text) else text + f"\n{key}={value}\n"
    try:
        path.write_text(text)
    except PermissionError:
        # /etc/podcast-cover-dms/env is root:dmbot 640 by design — the running
        # service can read its own credentials but never write them.
        print(f"\ncannot write to {path} — permission denied.", file=sys.stderr)
        print("Run this script as root instead (drop `-u dmbot`):", file=sys.stderr)
        print(f"    sudo {sys.executable} {' '.join(sys.argv)}", file=sys.stderr)
        raise SystemExit(1) from None
