"""Shared plumbing for the report-generation + HITL routes
(routes/report.py, routes/hitl.py).

Keeps the compiled report graph and session/state bookkeeping in one place
so both route modules resume against the exact same graph instance and
LangGraph thread (thread_id == session_id).
"""

from functools import lru_cache

from agents.qa_critic_agent import QACriticAgent
from agents.report_generator_agent import ReportGeneratorAgent
from api.session_store import SessionRecord, sessions
from graph.report_graph_builder import build_report_graph


@lru_cache(maxsize=1)
def get_report_graph():
    """Build the compiled report graph on first use, not at import time.

    Building eagerly at module scope would construct QACriticAgent (and thus
    the OpenRouter client) as a side effect of merely importing this module —
    breaking every route/test that imports api.main whenever no API key is
    configured yet.
    """
    return build_report_graph()


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
        "errors": list(state["errors"]),
    }
