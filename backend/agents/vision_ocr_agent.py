"""Vision/OCR Agent — scanned sheets, screenshots, handwritten forms → text.

Delegates to a vision-capable OpenRouter model via tools/ocr_tools.py rather
than a dedicated OCR engine (see that module's docstring for why). Failures
are recorded as ErrorRecords rather than raised, matching the Document
Ingestion Agent's error handling.
"""

from datetime import datetime, timezone

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
            # Resolved inside the try (not passed straight through) so both a
            # bad/missing API key (raised by get_llm_client() itself) and a
            # failed OCR call land in the same ErrorRecord path — and so
            # last_usage can be read off the same instance afterward.
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

        # getattr, not client.last_usage: test fakes for this agent only
        # implement .chat_with_image(), not the real LLMClient's usage attribute.
        usage = getattr(client, "last_usage", None)
        if usage is not None:
            state["token_usage"][f"{self.name}-{len(state['token_usage'])}"] = usage

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
