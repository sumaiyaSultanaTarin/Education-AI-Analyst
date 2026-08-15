"""`/sessions/{id}/hitl/{node}/approve|reject|retry` — resume the report
graph after it paused at the hitl_approval node's interrupt() (see
graph/report_graph_builder.py and api/routes/report.py).
"""

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from api.report_pipeline import (
    SessionNotFoundError,
    apply_result,
    get_record,
    report_graph,
    summarize,
    thread_config,
)
from api.routes.report import ReportRunResponse
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["hitl"])

# Only one HITL node exists today; kept as a set (not a single constant) so
# adding a second interrupt point later doesn't need a signature change.
_KNOWN_NODES = {"hitl_approval"}


class HitlRejectRequest(BaseModel):
    comment: str | None = None


def _validate_node(node: str) -> None:
    if node not in _KNOWN_NODES:
        raise HTTPException(status_code=404, detail=f"Unknown HITL node {node!r}")


def _resume(session_id: str, resume_value: dict) -> ReportRunResponse:
    try:
        record = get_record(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    report_graph.invoke(Command(resume=resume_value), config=thread_config(session_id))
    apply_result(session_id, record)
    return ReportRunResponse(**summarize(record))


@router.post("/{session_id}/hitl/{node}/approve", response_model=ReportRunResponse)
def approve(session_id: str, node: str) -> ReportRunResponse:
    _validate_node(node)
    logger.info("Session %s: HITL approved at %s", session_id, node)
    return _resume(session_id, {"action": "approved"})


@router.post("/{session_id}/hitl/{node}/reject", response_model=ReportRunResponse)
def reject(session_id: str, node: str, payload: HitlRejectRequest = HitlRejectRequest()) -> ReportRunResponse:
    _validate_node(node)
    logger.info("Session %s: HITL rejected at %s (%s)", session_id, node, payload.comment)
    return _resume(session_id, {"action": "rejected", "comment": payload.comment})


@router.post("/{session_id}/hitl/{node}/retry", response_model=ReportRunResponse)
def retry(session_id: str, node: str) -> ReportRunResponse:
    _validate_node(node)
    logger.info("Session %s: HITL retry at %s", session_id, node)
    return _resume(session_id, {"action": "retry"})
