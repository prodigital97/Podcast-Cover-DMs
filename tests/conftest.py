import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Set before any app import — config reads the environment at import time.
os.environ.setdefault("IG_ACCESS_TOKEN", "ig-token")
os.environ.setdefault("IG_APP_SECRET", "app-secret")
os.environ.setdefault("IG_VERIFY_TOKEN", "verify-me")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "tg-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "4242")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "tg-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-in-tests")
os.environ.setdefault("DASHBOARD_USERNAME", "test-admin")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-password")

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.config import config  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.sqlite3"))
    db.init()
    yield
