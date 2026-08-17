#!/usr/bin/env python3
"""Point the Telegram bot at this service.

    python3 scripts/set_telegram_webhook.py https://your-host.example.com

Registers <base-url>/webhooks/telegram with the secret token from the env
file (.env locally, /etc/podcast-cover-dms/env on the server — see
scripts/_envfile.py), and limits deliveries to the two update types the bot
actually handles. Read-only: never needs root to run.
"""
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _envfile  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    hostname_url = sys.argv[1]

    env_path = _envfile.resolve_path(sys.argv[:1])  # never treat the URL as a path override
    env = _envfile.read(env_path)
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    secret = env.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not token or not secret:
        print(f"TELEGRAM_BOT_TOKEN and/or TELEGRAM_WEBHOOK_SECRET are empty in {env_path}", file=sys.stderr)
        print("run scripts/telegram_setup.py first", file=sys.stderr)
        return 2

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={
            "url": f"{hostname_url.rstrip('/')}/webhooks/telegram",
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
