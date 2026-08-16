"""Report Generator Agent — compiles the DOCX report with citations back to
source documents (see docs/architecture.md §2.2).

Pulls the Data Analyst Agent's stats and Knowledge/RAG Agent's retrieval
results together. The RAG query used to source citations is the session
goal itself, so the report stays anchored to what the user actually asked
for.
"""

from datetime import datetime, timezone
from pathlib import Path

from agents.data_analyst_agent import DataAnalystAgent
from agents.knowledge_rag_agent import KnowledgeRAGAgent
from core.logging_config import get_logger
from graph.state import AnalystState
from tools.report_tools import build_report_docx

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORTS_DIR = _REPO_ROOT / "data" / "uploads"  # gitignored, same as uploaded documents


class ReportGeneratorAgent:
    name = "report_generator"

    def __init__(
        self, rag_agent: KnowledgeRAGAgent | None = None, reports_dir: Path | None = None
    ) -> None:
        self._rag_agent = rag_agent or KnowledgeRAGAgent()
        # Injectable so tests write to tmp_path instead of the real data/uploads.
        self._reports_dir = reports_dir or _REPORTS_DIR

    def generate(self, state: AnalystState) -> AnalystState:
        data_analysis = state["agent_outputs"].get(DataAnalystAgent.name, {})
        social_summary = state["agent_outputs"].get("social_intel")  # Phase 4, not built yet
        allowed_ids = {document["document_id"] for document in state["documents"]}
        citations = self._rag_agent.query(
            state["goal"], n_results=5, allowed_document_ids=allowed_ids
        )

        output_path = self._reports_dir / state["session_id"] / "report.docx"

        try:
            build_report_docx(
                str(output_path),
                goal=state["goal"],
                documents=list(state["documents"]),
                data_analysis=data_analysis,
                rag_citations=citations,
                social_summary=social_summary,
            )
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error(
                "Failed to generate report for session %s: %s", state["session_id"], exc
            )
            state["errors"].append({
                "agent_name": self.name,
                "document_id": None,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["agent_outputs"].setdefault(self.name, {})["report"] = {
            "path": str(output_path),
            "citation_count": len(citations),
            # QA/Critic re-reads these to check the report's claims against source data.
            "citations": citations,
        }
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Drafted report with {len(citations)} cited excerpt(s).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state
