"""Shared LangGraph state for the Supervisor + worker agents.

Mirrors docs/architecture.md §2.3/§2.4/§4 — keep this in sync if the ERD or
state shape changes there.
"""

from typing import Any, Literal, TypedDict


class TaskStep(TypedDict):
    step_id: str
    agent: str
    description: str
    status: Literal["pending", "running", "done", "failed"]
    depends_on: list[str]


class AgentMessage(TypedDict):
    from_agent: str
    to_agent: str
    content: str
    timestamp: str


class DocumentRef(TypedDict):
    document_id: str
    filename: str
    type: Literal["pdf", "docx", "pptx", "xlsx", "image", "social_csv"]
    path: str


class TokenCost(TypedDict):
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class ErrorRecord(TypedDict):
    agent_name: str
    document_id: str | None
    error_type: str
    message: str
    timestamp: str


class AnalystState(TypedDict):
    session_id: str
    goal: str
    plan: list[TaskStep]
    messages: list[AgentMessage]
    documents: list[DocumentRef]
    agent_outputs: dict[str, Any]
    memory_refs: list[str]
    hitl_status: dict[str, str]
    token_usage: dict[str, TokenCost]
    errors: list[ErrorRecord]
    # Scratch field the Supervisor node uses to hand off which document the
    # next worker node should process — not part of the persisted domain
    # model, just routing state for a single graph run.
    current_document_id: str | None


def new_state(session_id: str, goal: str) -> AnalystState:
    return AnalystState(
        session_id=session_id,
        goal=goal,
        plan=[],
        messages=[],
        documents=[],
        agent_outputs={},
        memory_refs=[],
        hitl_status={},
        token_usage={},
        errors=[],
        current_document_id=None,
    )
