"""`/sessions` endpoints — Phase 1 stub.

Backed by an in-memory dict, not the Postgres/SQLite `WorkflowSession` model
from docs/architecture.md §4 yet — that lands in Phase 3 alongside the rest
of the relational schema. This is enough to exercise the API contract that
the frontend and the other agents build against.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.supervisor import SupervisorAgent
from core.logging_config import get_logger
from graph.state import AnalystState, new_state

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@dataclass
class _SessionRecord:
    state: AnalystState
    created_at: str


_supervisor = SupervisorAgent()
_sessions: dict[str, _SessionRecord] = {}


class SessionCreateRequest(BaseModel):
    goal: str
    user_id: str


class SessionResponse(BaseModel):
    session_id: str
    goal: str
    status: Literal["planned"]
    plan: list[dict]
    created_at: str


@router.post("", response_model=SessionResponse)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    session_id = str(uuid.uuid4())
    state = new_state(session_id=session_id, goal=payload.goal)
    state = _supervisor.create_plan(state)
    created_at = datetime.now(timezone.utc).isoformat()
    _sessions[session_id] = _SessionRecord(state=state, created_at=created_at)

    logger.info("Created session %s for user %s", session_id, payload.user_id)
    return SessionResponse(
        session_id=session_id,
        goal=state["goal"],
        status="planned",
        plan=list(state["plan"]),
        created_at=created_at,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    record = _sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=record.state["session_id"],
        goal=record.state["goal"],
        status="planned",
        plan=list(record.state["plan"]),
        created_at=record.created_at,
    )
