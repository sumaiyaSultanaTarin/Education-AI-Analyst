"""`/sessions` endpoints.

Backed by an in-memory dict (api/session_store.py), not the Postgres/SQLite
`WorkflowSession` model from docs/architecture.md §4 yet — that lands in
Phase 3 alongside the rest of the relational schema.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.supervisor import SupervisorAgent
from api.session_store import SessionRecord, save_session, sessions
from core.logging_config import get_logger
from graph.graph_builder import build_graph
from graph.state import new_state

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])

_supervisor = SupervisorAgent()
_graph = build_graph()


class SessionCreateRequest(BaseModel):
    goal: str
    user_id: str


class SessionResponse(BaseModel):
    session_id: str
    goal: str
    # Must match SessionRecord.status (api/session_store.py) — that type grew
    # "awaiting_approval"/"report_ready" for the Phase 5 report/HITL pipeline,
    # so any session that reached generate-report used to 500 here on the
    # next GET, since those two values failed this narrower literal.
    status: Literal["planned", "completed", "awaiting_approval", "report_ready"]
    plan: list[dict]
    documents: list[dict]
    agent_outputs: dict
    messages: list[dict]
    token_usage: dict
    errors: list[dict]
    created_at: str


def _to_response(record: SessionRecord) -> SessionResponse:
    state = record.state
    return SessionResponse(
        session_id=state["session_id"],
        goal=state["goal"],
        status=record.status,
        plan=list(state["plan"]),
        documents=list(state["documents"]),
        agent_outputs=dict(state["agent_outputs"]),
        messages=list(state["messages"]),
        token_usage=dict(state["token_usage"]),
        errors=list(state["errors"]),
        created_at=record.created_at,
    )


def _get_record_or_404(session_id: str) -> SessionRecord:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.post("", response_model=SessionResponse)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    session_id = str(uuid.uuid4())
    state = new_state(session_id=session_id, goal=payload.goal)
    state = _supervisor.create_plan(state)
    record = SessionRecord(state=state, created_at=datetime.now(timezone.utc).isoformat())
    sessions[session_id] = record
    save_session(session_id, record)

    logger.info("Created session %s for user %s", session_id, payload.user_id)
    return _to_response(record)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    return _to_response(_get_record_or_404(session_id))


@router.post("/{session_id}/run", response_model=SessionResponse)
def run_session(session_id: str) -> SessionResponse:
    """Kick off the LangGraph run: ingest every uploaded document.

    Synchronous for now — runs to completion before responding. Streaming
    progress over WS /sessions/{id}/trace is future work, not Phase 2 scope.
    """
    record = _get_record_or_404(session_id)

    logger.info(
        "Running session %s (%d document(s))", session_id, len(record.state["documents"])
    )
    record.state = _graph.invoke(record.state)
    record.status = "completed"
    save_session(session_id, record)

    return _to_response(record)
