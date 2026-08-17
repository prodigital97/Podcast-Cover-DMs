#!/usr/bin/env python3
"""Finish Telegram setup: verify the bot token, find your chat id, generate the
webhook secret. Reads from the env file (see scripts/_envfile.py) and never
prints the token.

    python3 scripts/telegram_setup.py               # auto-detect the env file
    python3 scripts/telegram_setup.py /path/to/env   # or point at one explicitly

Writes the chat id and webhook secret back into that file, so it needs to run
as root on the server (the file is root:dmbot 640 — the service can read its
own credentials but not write them).

Run this, then message your bot anything (e.g. "hi") in Telegram, then run it
again — that second run is how it finds your chat id.
"""
import pathlib
import secrets
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _envfile  # noqa: E402


def main() -> int:
    env_path = _envfile.resolve_path(sys.argv)
    env = _envfile.read(env_path)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(f"TELEGRAM_BOT_TOKEN is empty in {env_path} — fill it in there first", file=sys.stderr)
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
        _envfile.write_value(env_path, "TELEGRAM_CHAT_ID", str(chat_id))
        print(f"✓ found your chat id ({who}) and saved it to {env_path}")

    if not env.get("TELEGRAM_WEBHOOK_SECRET", "").strip():
        _envfile.write_value(env_path, "TELEGRAM_WEBHOOK_SECRET", secrets.token_hex(16))
        print(f"✓ generated TELEGRAM_WEBHOOK_SECRET and saved it to {env_path}")
    else:
        print("✓ TELEGRAM_WEBHOOK_SECRET already set")

    env = _envfile.read(env_path)
    missing = [k for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET") if not env.get(k)]
    if missing:
        print(f"\nStill missing: {', '.join(missing)}")
        return 1
    print("\nTelegram side is fully configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
