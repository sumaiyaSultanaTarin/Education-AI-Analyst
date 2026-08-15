from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agents.knowledge_rag_agent import KnowledgeRAGAgent
from agents.qa_critic_agent import QACriticAgent
from agents.report_generator_agent import ReportGeneratorAgent
from api.main import app
from graph.report_graph_builder import build_report_graph

client = TestClient(app)


class _FakeLLMClient:
    def chat(self, messages, **kwargs):
        return "PASS"


def _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, reports_dir):
    """Swap the module-level report_graph singleton for one built entirely
    from fakes, so these tests don't need the real Chroma disk store, the
    real sentence-transformers model, or a real OpenRouter call.

    Both `api.report_pipeline.report_graph` (used by apply_result) and
    `api.routes.report.report_graph` (imported by name into that module at
    import time, so it needs its own patch) must be replaced.
    """
    rag_agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    graph = build_report_graph(
        rag_agent=rag_agent,
        report_generator_agent=ReportGeneratorAgent(rag_agent=rag_agent, reports_dir=reports_dir),
        qa_critic_agent=QACriticAgent(llm_client=_FakeLLMClient()),
        checkpointer=MemorySaver(),
    )
    monkeypatch.setattr("api.report_pipeline.report_graph", graph)
    monkeypatch.setattr("api.routes.report.report_graph", graph)
    return graph


def _create_session_with_xlsx(monkeypatch, tmp_path, sample_docs_dir):
    response = client.post("/sessions", json={"goal": "summarize term", "user_id": "u1"})
    session_id = response.json()["session_id"]

    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)
    with open(sample_docs_dir / "enrollment_results.xlsx", "rb") as f:
        client.post(
            f"/sessions/{session_id}/documents",
            files={
                "file": (
                    "enrollment_results.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    client.post(f"/sessions/{session_id}/run")
    return session_id


def test_generate_report_runs_pipeline_and_pauses_for_hitl(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")
    session_id = _create_session_with_xlsx(monkeypatch, tmp_path / "uploads", sample_docs_dir)

    response = client.post(f"/sessions/{session_id}/generate-report")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["qa_status"] == "pass"
    assert body["report_path"] is not None


def test_generate_report_without_documents_returns_400():
    response = client.post("/sessions", json={"goal": "no docs", "user_id": "u1"})
    session_id = response.json()["session_id"]

    response = client.post(f"/sessions/{session_id}/generate-report")

    assert response.status_code == 400


def test_generate_report_unknown_session_returns_404():
    response = client.post("/sessions/does-not-exist/generate-report")
    assert response.status_code == 404


def test_get_report_before_generation_returns_404():
    response = client.post("/sessions", json={"goal": "g", "user_id": "u1"})
    session_id = response.json()["session_id"]

    response = client.get(f"/sessions/{session_id}/report")

    assert response.status_code == 404
