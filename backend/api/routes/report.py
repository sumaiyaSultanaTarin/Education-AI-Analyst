"""`/sessions/{id}/generate-report` and `/sessions/{id}/report` — trigger and
fetch the Phase 3/5 analysis -> report -> QA -> HITL pipeline
(graph/report_graph_builder.py).

Separate from `/sessions/{id}/run` in sessions.py, which only runs document
intake (Phase 2) — this route runs *after* that one has populated
state["agent_outputs"] for every uploaded document.
"""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api import report_pipeline
from api.report_pipeline import (
    SessionNotFoundError,
    apply_result,
    get_record,
    summarize,
    thread_config,
)
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["report"])


class ReportRunResponse(BaseModel):
    session_id: str
    status: str
    hitl_status: dict[str, str]
    qa_status: str | None
    report_path: str | None
    report_pptx_path: str | None
    messages: list[dict]
    token_usage: dict
    errors: list[dict]


def _get_record_or_404(session_id: str):
    try:
        return get_record(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@router.post("/{session_id}/generate-report", response_model=ReportRunResponse)
def generate_report(session_id: str) -> ReportRunResponse:
    """Run data_analyst -> knowledge_rag -> report_generator -> qa_critic ->
    hitl_approval. Pauses at hitl_approval (interrupt()) until a human
    resolves it via POST /sessions/{id}/hitl/hitl_approval/{approve,reject,retry}.
    """
    record = _get_record_or_404(session_id)
    if not record.state["documents"]:
        raise HTTPException(status_code=400, detail="No documents to report on")

    logger.info("Generating report for session %s", session_id)
    report_pipeline.get_report_graph().invoke(record.state, config=thread_config(session_id))
    apply_result(session_id, record)
    return ReportRunResponse(**summarize(record))


@router.get("/{session_id}/report-status", response_model=ReportRunResponse)
def get_report_status(session_id: str) -> ReportRunResponse:
    """Read-only status check — reads back `record.state` as it stands right
    now, without invoking the report graph.

    The frontend caches the POST /generate-report and /hitl/* responses in
    st.session_state, but a full browser refresh wipes that (new WebSocket
    connection). This lets HITL Controls / Final Report restore the current
    status after a refresh without re-running the QA/Critic LLM call that
    POST /generate-report performs.
    """
    record = _get_record_or_404(session_id)
    return ReportRunResponse(**summarize(record))


@router.get("/{session_id}/report")
def get_report(
    session_id: str, format: Literal["docx", "pptx"] = Query("docx")
) -> FileResponse:
    record = _get_record_or_404(session_id)
    summary = summarize(record)
    report_path = summary["report_path"] if format == "docx" else summary["report_pptx_path"]
    if report_path is None or not Path(report_path).exists():
        raise HTTPException(status_code=404, detail="Report not generated yet")
    # The draft is written to disk before the graph pauses at hitl_approval,
    # so report_path already exists while a human still needs to sign off —
    # gate on record.status too, or this endpoint hands out unapproved drafts.
    if record.status != "report_ready":
        raise HTTPException(status_code=404, detail="Report not approved yet")
    return FileResponse(report_path, filename=Path(report_path).name)
