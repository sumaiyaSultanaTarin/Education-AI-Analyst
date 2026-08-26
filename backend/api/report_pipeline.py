"""Shared plumbing for the report-generation + HITL routes
(routes/report.py, routes/hitl.py).

Keeps the compiled report graph and session/state bookkeeping in one place
so both route modules resume against the exact same graph instance and
LangGraph thread (thread_id == session_id).
"""

import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from agents.qa_critic_agent import QACriticAgent
from agents.report_generator_agent import ReportGeneratorAgent
from api.session_store import SessionRecord, save_session, sessions
from graph.report_graph_builder import build_report_graph

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECKPOINT_DB_PATH = _REPO_ROOT / "data" / "checkpoints.db"


def _checkpointer_conn() -> sqlite3.Connection:
    # In-memory during tests (matches session_store's _in_tests rationale:
    # keeps the real data/checkpoints.db file untouched by test runs) — this
    # graph is @lru_cache'd, so one in-memory connection stays alive and
    # consistent for every test that reuses the cached graph within a run.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return sqlite3.connect(":memory:", check_same_thread=False)
    _CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(_CHECKPOINT_DB_PATH), check_same_thread=False)


@lru_cache(maxsize=1)
def get_report_graph():
    """Build the compiled report graph on first use, not at import time.

    Building eagerly at module scope would construct QACriticAgent (and thus
    the OpenRouter client) as a side effect of merely importing this module —
    breaking every route/test that imports api.main whenever no API key is
    configured yet.

    Checkpointed to SQLite (not the default MemorySaver): a session paused at
    the hitl_approval interrupt() needs its checkpoint to survive a backend
    restart, or resuming it later raises "no checkpoint found" instead of
    picking back up where it left off.
    """
    return build_report_graph(checkpointer=SqliteSaver(_checkpointer_conn()))


class SessionNotFoundError(Exception):
    """Raised when a session_id isn't in the in-memory session store."""


def get_record(session_id: str) -> SessionRecord:
    record = sessions.get(session_id)
    if record is None:
        raise SessionNotFoundError(session_id)
    return record


def thread_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def apply_result(session_id: str, record: SessionRecord) -> None:
    """Sync `record` from the checkpointer after an invoke/resume call.

    Reading back via get_state() (rather than trusting invoke()'s return
    value directly) is deliberate: when a run pauses on interrupt(),
    `snapshot.next` being non-empty is the documented, version-stable way to
    detect "still paused" — relying on exactly what keys invoke() merges into
    its return dict around an interrupt is not something worth hard-coding.
    """
    snapshot = get_report_graph().get_state(thread_config(session_id))
    record.state = snapshot.values
    record.status = "awaiting_approval" if snapshot.next else "report_ready"
    save_session(session_id, record)


def summarize(record: SessionRecord) -> dict:
    state = record.state
    qa = state["agent_outputs"].get(QACriticAgent.name, {})
    report = state["agent_outputs"].get(ReportGeneratorAgent.name, {}).get("report", {})
    return {
        "session_id": state["session_id"],
        "status": record.status,
        "hitl_status": dict(state["hitl_status"]),
        "qa_status": qa.get("status"),
        "report_path": report.get("path"),
        "report_pptx_path": report.get("pptx_path"),
        "messages": list(state["messages"]),
        "token_usage": dict(state["token_usage"]),
        "errors": list(state["errors"]),
    }
