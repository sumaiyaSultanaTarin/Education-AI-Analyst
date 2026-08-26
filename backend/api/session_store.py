"""Session store shared across route modules — in-memory dict, backed by a
SQLite file so a backend restart doesn't wipe every session (including one
paused mid-HITL-approval). `sessions` stays a plain dict, and every route
that mutates a record still just mutates `record.state`/`record.status` in
place exactly as before; call `save_session(session_id, record)` right after
so the on-disk copy doesn't drift from what's actually in memory.

Not the full Postgres/SQLite WorkflowSession relational model from
docs/architecture.md §4 — that's a bigger schema change. This is the
minimum needed for a session to survive a restart.
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from graph.state import AnalystState

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _REPO_ROOT / "data" / "sessions.db"


@dataclass
class SessionRecord:
    state: AnalystState
    created_at: str
    # "awaiting_approval"/"report_ready" added for the Phase 5 report/HITL
    # pipeline (api/report_pipeline.py) — "planned"/"completed" are Tarin's
    # existing Phase 1/2 intake states, left as-is.
    status: Literal["planned", "completed", "awaiting_approval", "report_ready"] = "planned"


def _in_tests() -> bool:
    # Pytest sets this for the duration of every test — used here (not a
    # fixture) so no test file has to opt in, and the real data/sessions.db
    # never gets polluted with test session rows.
    return "PYTEST_CURRENT_TEST" in os.environ


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        "session_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
        "created_at TEXT NOT NULL, state_json TEXT NOT NULL)"
    )
    return conn


def save_session(session_id: str, record: SessionRecord) -> None:
    """Persist the current state/status snapshot. Call right after a route
    finishes mutating record.state or record.status."""
    if _in_tests():
        return
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, status, created_at, state_json) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "status=excluded.status, state_json=excluded.state_json",
            (session_id, record.status, record.created_at, json.dumps(record.state)),
        )


def load_sessions_from_disk() -> dict[str, SessionRecord]:
    """Rebuild the in-memory `sessions` dict from data/sessions.db.

    Called once from api.main's startup handler — not at import time, so
    importing this module (or api.main, transitively) stays a pure, side
    effect-free operation for tests, matching report_pipeline.get_report_graph's
    same lazy-build rationale.
    """
    if _in_tests() or not _DB_PATH.exists():
        return {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT session_id, status, created_at, state_json FROM sessions"
        ).fetchall()
    return {
        session_id: SessionRecord(
            state=json.loads(state_json), created_at=created_at, status=status
        )
        for session_id, status, created_at, state_json in rows
    }


sessions: dict[str, SessionRecord] = {}
