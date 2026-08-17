#!/usr/bin/env python3
"""Finish Telegram setup: verify the bot token, find your chat id, generate the
webhook secret. Reads TELEGRAM_BOT_TOKEN from the env file and never prints it.

    python3 scripts/telegram_setup.py               # auto-detect the env file
    python3 scripts/telegram_setup.py /path/to/env   # or point at one explicitly

Run this, then message your bot anything (e.g. "hi") in Telegram, then run it
again — that second run is how it finds your chat id.
"""
import pathlib
import re
import secrets
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Local dev keeps credentials in .env at the project root. deploy/setup.sh keeps
# them in /etc instead, deliberately outside the git-managed directory, so a
# redeploy (which replaces ROOT wholesale) can never touch them. Check both.
CANDIDATE_ENV_PATHS = [ROOT / ".env", pathlib.Path("/etc/podcast-cover-dms/env")]


def resolve_env_path() -> pathlib.Path:
    if len(sys.argv) > 1:
        path = pathlib.Path(sys.argv[1])
        if not path.exists():
            print(f"no such file: {path}", file=sys.stderr)
            raise SystemExit(2)
        return path
    for path in CANDIDATE_ENV_PATHS:
        if path.exists():
            return path
    tried = ", ".join(str(p) for p in CANDIDATE_ENV_PATHS)
    print(f"no env file found — tried: {tried}", file=sys.stderr)
    print("copy .env.example to .env (local) or check the deploy setup (server)", file=sys.stderr)
    raise SystemExit(2)


ENV_PATH = resolve_env_path()


def read_env() -> dict[str, str]:
    values = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env_value(key: str, value: str) -> None:
    text = ENV_PATH.read_text()
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"{key}={value}", text)
    else:
        text += f"\n{key}={value}\n"
    ENV_PATH.write_text(text)


def main() -> int:
    env = read_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(f"TELEGRAM_BOT_TOKEN is empty in {ENV_PATH} — fill it in there first", file=sys.stderr)
        return 2

    api = f"https://api.telegram.org/bot{token}"

    me = httpx.get(f"{api}/getMe", timeout=15).json()
    if not me.get("ok"):
        print(f"getMe failed — is the token right? {me}", file=sys.stderr)
        return 1
    bot = me["result"]
    print(f"✓ token is valid — this is @{bot['username']} ({bot.get('first_name', '')})")

    existing_chat_id = env.get("TELEGRAM_CHAT_ID", "").strip()
    updates = httpx.get(f"{api}/getUpdates", timeout=15).json()
    chat_ids: dict[int, str] = {}
    for update in updates.get("result", []):
        msg = update.get("message") or update.get("channel_post")
        if msg and "chat" in msg:
            chat = msg["chat"]
            chat_ids[chat["id"]] = chat.get("username") or chat.get("first_name", "?")

    if not chat_ids:
        print(
            "\nNo messages seen yet. In Telegram, open a chat with "
            f"@{bot['username']} and send it anything (e.g. \"hi\"), "
            "then run this script again."
        )
        if not existing_chat_id:
            return 0
    elif len(chat_ids) > 1:
        print("\nSaw messages from more than one chat — pick yours and set TELEGRAM_CHAT_ID manually:")
        for chat_id, who in chat_ids.items():
            print(f"  {chat_id}  ({who})")
    else:
        (chat_id, who), = chat_ids.items()
        write_env_value("TELEGRAM_CHAT_ID", str(chat_id))
        print(f"✓ found your chat id ({who}) and saved it to {ENV_PATH}")

    if not env.get("TELEGRAM_WEBHOOK_SECRET", "").strip():
        write_env_value("TELEGRAM_WEBHOOK_SECRET", secrets.token_hex(16))
        print(f"✓ generated TELEGRAM_WEBHOOK_SECRET and saved it to {ENV_PATH}")
    else:
        print("✓ TELEGRAM_WEBHOOK_SECRET already set")

    env = read_env()
    missing = [k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET") if not env.get(k)]
    if missing:
        print(f"\nStill missing: {', '.join(missing)}")
        return 1
    print("\nTelegram side is fully configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
