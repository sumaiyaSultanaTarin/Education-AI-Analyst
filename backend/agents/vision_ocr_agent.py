"""Vision/OCR Agent — scanned sheets, screenshots, handwritten forms → text.

Delegates to a vision-capable OpenRouter model via tools/ocr_tools.py rather
than a dedicated OCR engine (see that module's docstring for why). Failures
are recorded as ErrorRecords rather than raised, matching the Document
Ingestion Agent's error handling.
"""

from datetime import datetime, timezone

from core.cost_tracker import record_usage
from core.llm_client import LLMClient, get_llm_client
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
            # Resolved here, inside the try (not left to ocr_tools' own
            # internal default) so we can read get_last_usage() off the exact
            # client instance that made the call, for token/cost tracking —
            # but resolving it still has to stay inside this try/except,
            # since get_llm_client() itself can raise (e.g. no API key
            # configured) and that must become an ErrorRecord too, not an
            # uncaught exception out of process_image().
            client = self._llm_client or get_llm_client()
            text = extract_text_from_image(document["path"], llm_client=client)
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

        record_usage(state, self.name, client.get_last_usage())

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
