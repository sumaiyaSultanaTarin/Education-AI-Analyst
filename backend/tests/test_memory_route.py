from fastapi.testclient import TestClient

from agents.knowledge_rag_agent import KnowledgeRAGAgent
from api.main import app

client = TestClient(app)


def _install_fake_rag_agent(monkeypatch, chroma_collection, fake_embed_fn):
    agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    monkeypatch.setattr("api.routes.memory._rag_agent", agent)
    return agent


def test_query_memory_returns_indexed_chunks_for_this_session(
    monkeypatch, chroma_collection, fake_embed_fn
):
    rag_agent = _install_fake_rag_agent(monkeypatch, chroma_collection, fake_embed_fn)

    response = client.post("/sessions", json={"goal": "test", "user_id": "u1"})
    session_id = response.json()["session_id"]

    from api.session_store import sessions

    sessions[session_id].state["documents"] = [
        {"document_id": "doc-1", "filename": "notes.pdf", "type": "pdf", "path": "unused"}
    ]
    sessions[session_id].state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"pages": [{"page_number": 1, "text": "late assignment submissions rose", "tables": []}]}
    }
    rag_agent.index_all(sessions[session_id].state)

    response = client.get(f"/sessions/{session_id}/memory", params={"query": "late submissions"})

    assert response.status_code == 200
    hits = response.json()
    assert len(hits) == 1
    assert hits[0]["filename"] == "notes.pdf"


def test_query_memory_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/memory", params={"query": "anything"})
    assert response.status_code == 404
