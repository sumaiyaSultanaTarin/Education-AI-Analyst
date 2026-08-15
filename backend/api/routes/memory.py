"""`/sessions/{id}/memory` — query the Chroma knowledge base for this session.

Owned by the Knowledge/RAG Agent (see agents/knowledge_rag_agent.py); this
route is a thin read-only wrapper so the UI (Memory Viewer panel) or other
tools can search what's been indexed without kicking off a full report run.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agents.knowledge_rag_agent import KnowledgeRAGAgent
from api.session_store import sessions

router = APIRouter(prefix="/sessions", tags=["memory"])
_rag_agent = KnowledgeRAGAgent()


class MemoryHit(BaseModel):
    text: str
    filename: str
    document_id: str
    chunk_index: int
    distance: float


@router.get("/{session_id}/memory", response_model=list[MemoryHit])
def query_memory(session_id: str, query: str = Query(..., min_length=1)) -> list[MemoryHit]:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    allowed_ids = {document["document_id"] for document in record.state["documents"]}
    hits = _rag_agent.query(query, allowed_document_ids=allowed_ids)
    return [MemoryHit(**hit) for hit in hits]
