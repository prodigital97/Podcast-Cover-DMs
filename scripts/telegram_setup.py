#!/usr/bin/env python3
"""Finish Telegram setup: verify the bot token, find your chat id, generate the
webhook secret. Reads TELEGRAM_BOT_TOKEN from .env and never prints it.

    python3 scripts/telegram_setup.py

Run this, then message your bot anything (e.g. "hi") in Telegram, then run it
again — that second run is how it finds your chat id.
"""
import pathlib
import re
import secrets
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        print(f"no .env at {ENV_PATH} — copy .env.example to .env first", file=sys.stderr)
        raise SystemExit(2)
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
        print("TELEGRAM_BOT_TOKEN is empty in .env — paste it in there first, not here", file=sys.stderr)
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
        print(f"✓ found your chat id ({who}) and saved it to .env")

    if not env.get("TELEGRAM_WEBHOOK_SECRET", "").strip():
        write_env_value("TELEGRAM_WEBHOOK_SECRET", secrets.token_hex(16))
        print("✓ generated TELEGRAM_WEBHOOK_SECRET and saved it to .env")
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
