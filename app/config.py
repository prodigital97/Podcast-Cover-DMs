"""Configuration, all from the environment. See .env.example."""
from __future__ import annotations

import os


def _req(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set — see .env.example")
    return value


class Config:
    # --- Instagram ---------------------------------------------------------
    # Instagram Login tokens use graph.instagram.com and the "me" node.
    # Facebook Login for Business tokens use graph.facebook.com and the IG user id.
    IG_BASE_URL = os.environ.get("IG_BASE_URL", "https://graph.instagram.com")
    IG_API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
    # The node messages are sent from: "me" for Instagram Login, else the IG user id.
    IG_SEND_NODE = os.environ.get("IG_SEND_NODE", "me")

    # Set only if you also hold a Facebook Login token with instagram_basic — it is
    # the only way to read a sender's bio (via business_discovery). Optional: without
    # it, leads are built from the messaging profile alone and bio stays unknown.
    FB_GRAPH_URL = os.environ.get("FB_GRAPH_URL", "https://graph.facebook.com")
    IG_USER_ID = os.environ.get("IG_USER_ID", "")
    IG_DISCOVERY_TOKEN = os.environ.get("IG_DISCOVERY_TOKEN", "")

    # Extend the messaging window from 24h to 7d using the HUMAN_AGENT tag. Requires
    # the human_agent permission to be approved for your app; leave off until it is.
    IG_USE_HUMAN_AGENT_TAG = os.environ.get("IG_USE_HUMAN_AGENT_TAG", "") == "1"

    # --- Telegram ----------------------------------------------------------
    # Only this chat id may approve. Anything from another chat is ignored.
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

    # --- Model -------------------------------------------------------------
    # "anthropic" or "gemini". Both use native structured outputs.
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
    ANTHROPIC_EFFORT = os.environ.get("ANTHROPIC_EFFORT", "medium")
    # Set this to whichever Flash model you actually want — an unknown id is a
    # 404 at draft time, not at startup.
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")

    # --- Storage -----------------------------------------------------------
    DB_PATH = os.environ.get("DB_PATH", "podcast_cover_dms.sqlite3")

    @staticmethod
    def ig_token() -> str:
        return _req("IG_ACCESS_TOKEN")

    @staticmethod
    def ig_app_secret() -> str:
        return _req("IG_APP_SECRET")

    @staticmethod
    def ig_verify_token() -> str:
        return _req("IG_VERIFY_TOKEN")

    @staticmethod
    def telegram_token() -> str:
        return _req("TELEGRAM_BOT_TOKEN")

    @staticmethod
    def gemini_key() -> str:
        return _req("GEMINI_API_KEY")

    # An instance method, not a classmethod: every setting is read through the
    # `config` instance, and a classmethod would silently ignore overrides on it.
    def model_id(self) -> str:
        return self.GEMINI_MODEL if self.LLM_PROVIDER == "gemini" else self.ANTHROPIC_MODEL

    @staticmethod
    def telegram_secret() -> str:
        """Shared secret Telegram echoes in X-Telegram-Bot-Api-Secret-Token."""
        return _req("TELEGRAM_WEBHOOK_SECRET")


config = Config()
