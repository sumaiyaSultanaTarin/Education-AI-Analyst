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

    def get_last_usage(self):
        return None


def _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, reports_dir):
    """Swap the lazily-built report graph for one built entirely from fakes,
    so these tests don't need the real Chroma disk store, the real
    sentence-transformers model, or a real OpenRouter call.

    Patching `api.report_pipeline.get_report_graph` is enough: routes/report.py
    calls `report_pipeline.get_report_graph()` at request time rather than
    binding its own module-level name, so there's only one place to patch.
    """
    rag_agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    graph = build_report_graph(
        rag_agent=rag_agent,
        report_generator_agent=ReportGeneratorAgent(rag_agent=rag_agent, reports_dir=reports_dir),
        qa_critic_agent=QACriticAgent(llm_client=_FakeLLMClient()),
        checkpointer=MemorySaver(),
    )
    monkeypatch.setattr("api.report_pipeline.get_report_graph", lambda: graph)
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


def test_get_session_after_generate_report_does_not_500(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    """SessionResponse.status (routes/sessions.py) must accept every value
    SessionRecord.status can hold, including the "awaiting_approval" and
    "report_ready" states generate-report sets — otherwise GET /sessions/{id}
    500s on any session that has ever generated a report."""
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")
    session_id = _create_session_with_xlsx(monkeypatch, tmp_path / "uploads", sample_docs_dir)
    client.post(f"/sessions/{session_id}/generate-report")

    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"


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


def test_get_report_before_hitl_approval_returns_404(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    """The draft file is written to disk before the graph pauses for human
    approval, so GET /report must check approval status too, not just
    whether the file exists — otherwise it hands out unapproved drafts."""
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")
    session_id = _create_session_with_xlsx(monkeypatch, tmp_path / "uploads", sample_docs_dir)
    client.post(f"/sessions/{session_id}/generate-report")

    response = client.get(f"/sessions/{session_id}/report")

    assert response.status_code == 404
