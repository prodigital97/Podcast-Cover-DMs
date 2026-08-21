#!/usr/bin/env python3
"""Subscribe the Instagram account / page to this app's webhooks.

    python3 scripts/subscribe_instagram_webhook.py

Calls Meta's /subscribed_apps endpoint with IG_ACCESS_TOKEN to ensure Instagram
delivers incoming direct messages to the registered webhook URL.
"""
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _envfile  # noqa: E402


def main() -> int:
    env_path = _envfile.resolve_path(sys.argv)
    env = _envfile.read(env_path)

    token = env.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print(f"IG_ACCESS_TOKEN is empty in {env_path}", file=sys.stderr)
        return 2

    base_url = env.get("IG_BASE_URL", "https://graph.instagram.com").rstrip("/")
    api_version = env.get("IG_API_VERSION", "v23.0").strip("/")
    send_node = env.get("IG_SEND_NODE", "me").strip("/")

    # 1. Verify token & identity
    me_url = f"{base_url}/{api_version}/{send_node}"
    print(f"Checking token identity against {me_url}...")
    try:
        me_resp = httpx.get(
            me_url,
            params={"fields": "id,username", "access_token": token},
            timeout=15,
        )
        me_data = me_resp.json()
    except Exception as exc:
        print(f"Failed to connect to Meta API: {exc}", file=sys.stderr)
        return 1

    if "error" in me_data:
        print(f"Token check failed: {me_data['error']}", file=sys.stderr)
        return 1

    print(f"✓ Token valid for ID: {me_data.get('id')} (@{me_data.get('username', 'unknown')})")

    # 2. Subscribe account to webhooks
    sub_url = f"{base_url}/{api_version}/{send_node}/subscribed_apps"
    print(f"\nSubscribing account to messaging webhooks at {sub_url}...")
    sub_resp = httpx.post(
        sub_url,
        params={
            "subscribed_fields": "messages,messaging_postbacks",
            "access_token": token,
        },
        timeout=15,
    )
    sub_data = sub_resp.json()
    print(f"Response: {sub_data}")

    # 3. Verify active subscriptions
    get_sub_resp = httpx.get(
        sub_url,
        params={"access_token": token},
        timeout=15,
    )
    print(f"\nActive subscriptions: {get_sub_resp.text}")

    if sub_data.get("success") is True or sub_resp.status_code == 200:
        print("\n✓ Instagram account is successfully subscribed to messaging webhooks!")
        return 0
    else:
        print("\n⚠️ Subscription response was not explicit success. Check output above.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
