#!/usr/bin/env python3
"""Point the Telegram bot at this service.

    python3 scripts/set_telegram_webhook.py https://your-host.example.com

Registers <base-url>/webhooks/telegram with the secret token from the environment,
and limits deliveries to the two update types the bot actually handles.
"""
import os
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not token or not secret:
        print("set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first", file=sys.stderr)
        return 2

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={
            "url": f"{sys.argv[1].rstrip('/')}/webhooks/telegram",
            "secret_token": secret,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        },
        timeout=20,
    )
    print(response.text)
    return 0 if response.json().get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
