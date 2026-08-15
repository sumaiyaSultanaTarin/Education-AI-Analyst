"""Knowledge/RAG Agent — owns Chroma, indexes ingested text, and answers
semantic queries for other agents and the final report (see
docs/architecture.md §2.2/§2.4).

Runs after Document Ingestion / Vision-OCR have populated
state["agent_outputs"] — not part of that intake loop. See
graph/report_graph_builder.py for how this agent is wired into the
analysis -> report -> QA -> HITL pipeline.
"""

from datetime import datetime, timezone
from typing import Any

from agents.document_ingestion_agent import DocumentIngestionAgent
from agents.vision_ocr_agent import VisionOCRAgent
from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
from memory.chroma_store import get_collection
from tools.embedding_tools import embed_texts
from tools.rag_tools import EmbedFn, chunk_text, index_chunks, query_collection

logger = get_logger(__name__)


def _extract_plain_text(document_type: str, content: dict) -> str:
    """Flatten a Document Ingestion / Vision-OCR content dict to plain text for chunking."""
    if document_type == "image":
        return content.get("text", "")
    if document_type == "pdf":
        return "\n\n".join(page["text"] for page in content.get("pages", []) if page["text"])
    if document_type == "docx":
        return "\n".join(content.get("paragraphs", []))
    if document_type == "pptx":
        lines: list[str] = []
        for slide in content.get("slides", []):
            lines.extend(slide["text"])
        return "\n".join(lines)
    if document_type == "xlsx":
        lines = []
        for sheet_name, rows in content.get("sheets", {}).items():
            for row in rows:
                lines.append(f"{sheet_name}: " + ", ".join(f"{k}={v}" for k, v in row.items()))
        return "\n".join(lines)
    return ""


class KnowledgeRAGAgent:
    name = "knowledge_rag"

    def __init__(self, collection: Any | None = None, embed_fn: EmbedFn | None = None) -> None:
        self._collection = collection
        # Injectable so tests don't have to download the real
        # sentence-transformers model (see tools/embedding_tools.py).
        self._embed_fn: EmbedFn = embed_fn or embed_texts

    def _get_collection(self) -> Any:
        return self._collection if self._collection is not None else get_collection("documents")

    def index_document(self, state: AnalystState, document: DocumentRef) -> AnalystState:
        """Chunk + embed the already-ingested content for one document into Chroma."""
        content = state["agent_outputs"].get(DocumentIngestionAgent.name, {}).get(
            document["document_id"]
        ) or state["agent_outputs"].get(VisionOCRAgent.name, {}).get(document["document_id"])

        if content is None:
            return state  # ingestion failed earlier for this document — nothing to index

        text = _extract_plain_text(document["type"], content)
        chunks = chunk_text(text)

        try:
            chunk_ids = index_chunks(
                self._get_collection(),
                document["document_id"],
                document["filename"],
                chunks,
                embed_fn=self._embed_fn,
            )
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Failed to index %s: %s", document["filename"], exc)
            state["errors"].append({
                "agent_name": self.name,
                "document_id": document["document_id"],
                "error_type": type(exc).__name__,
                "message": f"{document['filename']}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["memory_refs"].extend(chunk_ids)
        state["agent_outputs"].setdefault(self.name, {})[document["document_id"]] = {
            "chunk_count": len(chunks)
        }
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Indexed {document['filename']} ({len(chunks)} chunk(s)).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state

    def index_all(self, state: AnalystState) -> AnalystState:
        """Index every document in state["documents"] — used as a report-graph node."""
        for document in state["documents"]:
            state = self.index_document(state, document)
        return state

    def query(
        self, query: str, n_results: int = 5, allowed_document_ids: set[str] | None = None
    ) -> list[dict]:
        """Semantic lookup for other agents/the final report — not a graph node itself.

        `allowed_document_ids`, when given, filters results down to one
        session's own documents — the Chroma collection isn't session-scoped,
        so without this a query could surface another session's content.
        """
        hits = query_collection(
            self._get_collection(), query, n_results=n_results, embed_fn=self._embed_fn
        )
        if allowed_document_ids is not None:
            hits = [hit for hit in hits if hit["document_id"] in allowed_document_ids]
        return hits
