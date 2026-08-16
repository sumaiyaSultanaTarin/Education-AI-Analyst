"""`/sessions/{id}/messages` — agent-to-agent communication log.

Backs the Communication Log frontend panel (docs/architecture.md §6). The
data already exists — every agent appends to state["messages"] as it runs
(see agents/*.py) — this route just exposes it read-only.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.session_store import sessions

router = APIRouter(prefix="/sessions", tags=["messages"])


class AgentMessageResponse(BaseModel):
    from_agent: str
    to_agent: str
    content: str
    timestamp: str


@router.get("/{session_id}/messages", response_model=list[AgentMessageResponse])
def get_messages(session_id: str) -> list[AgentMessageResponse]:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return [AgentMessageResponse(**message) for message in record.state["messages"]]
