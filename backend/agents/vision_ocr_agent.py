"""Vision/OCR Agent — scanned sheets, screenshots, handwritten forms → text.

Delegates to a vision-capable OpenRouter model via tools/ocr_tools.py rather
than a dedicated OCR engine (see that module's docstring for why). Failures
are recorded as ErrorRecords rather than raised, matching the Document
Ingestion Agent's error handling.
"""

from datetime import datetime, timezone

from core.llm_client import LLMClient
from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
from tools.ocr_tools import extract_text_from_image

logger = get_logger(__name__)


class VisionOCRAgent:
    name = "vision_ocr"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def process_image(self, state: AnalystState, document: DocumentRef) -> AnalystState:
        if document["type"] != "image":
            raise ValueError(
                f"vision_ocr only handles type='image', got {document['type']!r}"
            )

        try:
            text = extract_text_from_image(document["path"], llm_client=self._llm_client)
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Failed to OCR %s: %s", document["filename"], exc)
            state["errors"].append({
                "agent_name": self.name,
                "document_id": document["document_id"],
                "error_type": type(exc).__name__,
                "message": f"{document['filename']}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["agent_outputs"].setdefault(self.name, {})[document["document_id"]] = {
            "text": text
        }
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"OCR'd {document['filename']}.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state
