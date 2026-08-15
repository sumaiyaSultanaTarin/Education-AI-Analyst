"""Document Ingestion Agent — PDF/DOCX/PPTX/XLSX to structured text/tables.

Dispatches to the format-specific tool in backend/tools/ and records the
result on state["agent_outputs"]. Parse failures are recorded as
ErrorRecords rather than raised, so one bad document doesn't take down the
whole run.
"""

from datetime import datetime, timezone

from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
from tools.docx_tools import extract_docx_content
from tools.pdf_tools import extract_pdf_content
from tools.pptx_tools import extract_pptx_content
from tools.xlsx_tools import extract_xlsx_content

logger = get_logger(__name__)

_EXTRACTORS = {
    "pdf": extract_pdf_content,
    "docx": extract_docx_content,
    "pptx": extract_pptx_content,
    "xlsx": extract_xlsx_content,
}


class DocumentIngestionAgent:
    name = "document_ingestion"

    def ingest(self, state: AnalystState, document: DocumentRef) -> AnalystState:
        extractor = _EXTRACTORS.get(document["type"])
        if extractor is None:
            raise ValueError(
                f"document_ingestion cannot handle type={document['type']!r}; "
                "images go through the vision_ocr agent instead"
            )

        try:
            content = extractor(document["path"])
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Failed to ingest %s: %s", document["filename"], exc)
            state["errors"].append({
                "agent_name": self.name,
                "error_type": type(exc).__name__,
                "message": f"{document['filename']}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["agent_outputs"].setdefault(self.name, {})[document["document_id"]] = content
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Ingested {document['filename']} ({document['type']}).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state
