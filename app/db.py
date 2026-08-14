"""SQLite store: leads, message history, and pending approvals.

One file, no migrations framework — the schema is small enough that `init()` is
idempotent and additive. Every write goes through a function here so the WAL/timeout
settings are applied in one place.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from app.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    igsid           TEXT PRIMARY KEY,
    handle          TEXT,
    podcast_name    TEXT,
    bio             TEXT,
    about           TEXT,
    audience_size   TEXT,
    voice_notes     TEXT,
    status          TEXT NOT NULL DEFAULT 'first_contact',
    needs           TEXT NOT NULL DEFAULT 'nothing stated yet',
    offered         TEXT NOT NULL DEFAULT 'nothing yet',
    price           TEXT NOT NULL DEFAULT 'not discussed',
    commitments     TEXT NOT NULL DEFAULT 'none',
    enriched_at     REAL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    igsid       TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('them', 'pronoy')),
    text        TEXT NOT NULL,
    mid         TEXT UNIQUE,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_lead ON messages (igsid, created_at);

CREATE TABLE IF NOT EXISTS approvals (
    id                  TEXT PRIMARY KEY,
    igsid               TEXT NOT NULL,
    incoming_text       TEXT NOT NULL,
    read                TEXT NOT NULL,
    stage               TEXT NOT NULL,
    drafts_json         TEXT NOT NULL,
    state               TEXT NOT NULL,
    telegram_message_id INTEGER,
    sent_text           TEXT,
    created_at          REAL NOT NULL,
    resolved_at         REAL
);
CREATE INDEX IF NOT EXISTS approvals_open ON approvals (state, created_at);
"""

LEAD_FIELDS = (
    "handle", "podcast_name", "bio", "about", "audience_size", "voice_notes",
    "status", "needs", "offered", "price", "commitments",
)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- leads -----------------------------------------------------------------

def get_lead(igsid: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE igsid = ?", (igsid,)).fetchone()
    return dict(row) if row else None


def upsert_lead(igsid: str, **fields: Any) -> dict[str, Any]:
    """Create the lead if new, then apply only the non-None fields given."""
    now = time.time()
    updates = {k: v for k, v in fields.items() if k in LEAD_FIELDS and v is not None}
    with connect() as conn:
        conn.execute(
            "INSERT INTO leads (igsid, created_at, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(igsid) DO NOTHING",
            (igsid, now, now),
        )
        if updates:
            assignments = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE leads SET {assignments}, updated_at = ? WHERE igsid = ?",
                (*updates.values(), now, igsid),
            )
    return get_lead(igsid)  # type: ignore[return-value]


def mark_enriched(igsid: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE leads SET enriched_at = ? WHERE igsid = ?", (time.time(), igsid))


# --- messages --------------------------------------------------------------

def add_message(igsid: str, direction: str, text: str, mid: str | None = None) -> bool:
    """Returns False if this mid was already recorded (Meta retries webhooks)."""
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO messages (id, igsid, direction, text, mid, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, igsid, direction, text, mid, time.time()),
            )
        except sqlite3.IntegrityError:
            return False
    return True


def thread(igsid: str, limit: int = 40) -> str:
    """The conversation as the prompt wants it: oldest first, speaker-prefixed."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT direction, text FROM messages WHERE igsid = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (igsid, limit),
        ).fetchall()
    return "\n".join(f"{r['direction']}: {r['text']}" for r in reversed(rows))


def inbound_count(igsid: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE igsid = ? AND direction = 'them'",
            (igsid,),
        ).fetchone()
    return int(row["n"])


def last_inbound_at(igsid: str) -> float | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT MAX(created_at) AS t FROM messages WHERE igsid = ? AND direction = 'them'",
            (igsid,),
        ).fetchone()
    return row["t"]


# --- approvals -------------------------------------------------------------

def create_approval(igsid: str, incoming_text: str, drafts: dict[str, Any]) -> str:
    approval_id = uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            "INSERT INTO approvals (id, igsid, incoming_text, read, stage, drafts_json,"
            " state, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
            (
                approval_id, igsid, incoming_text, drafts["read"], drafts["stage"],
                json.dumps(drafts["drafts"]), time.time(),
            ),
        )
    return approval_id


def get_approval(approval_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        return None
    approval = dict(row)
    approval["drafts"] = json.loads(approval.pop("drafts_json"))
    return approval


def set_approval_message_id(approval_id: str, message_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE approvals SET telegram_message_id = ? WHERE id = ?",
            (message_id, approval_id),
        )


def set_approval_state(approval_id: str, state: str, sent_text: str | None = None) -> None:
    resolved = time.time() if state in {"sent", "skipped"} else None
    with connect() as conn:
        conn.execute(
            "UPDATE approvals SET state = ?, sent_text = COALESCE(?, sent_text),"
            " resolved_at = ? WHERE id = ?",
            (state, sent_text, resolved, approval_id),
        )


def awaiting_edit() -> dict[str, Any] | None:
    """The approval currently waiting on typed replacement text, if any."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM approvals WHERE state = 'awaiting_edit'"
            " ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
    return get_approval(row["id"]) if row else None


def open_approval_for(igsid: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM approvals WHERE igsid = ? AND state IN ('open', 'awaiting_edit')"
            " ORDER BY created_at DESC LIMIT 1",
            (igsid,),
        ).fetchone()
    return get_approval(row["id"]) if row else None
