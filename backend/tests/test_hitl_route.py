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
    """Swap the lazily-built report graph for one built entirely from fakes.

    Patching `api.report_pipeline.get_report_graph` is enough: routes/report.py
    and routes/hitl.py both call `report_pipeline.get_report_graph()` at
    request time rather than binding their own module-level name, so there's
    only one place to patch.
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


def _session_awaiting_approval(monkeypatch, tmp_path, sample_docs_dir):
    response = client.post("/sessions", json={"goal": "summarize term", "user_id": "u1"})
    session_id = response.json()["session_id"]

    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path / "uploads")
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
    client.post(f"/sessions/{session_id}/generate-report")
    return session_id


def test_approve_completes_the_run(monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn):
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")
    session_id = _session_awaiting_approval(monkeypatch, tmp_path, sample_docs_dir)

    response = client.post(f"/sessions/{session_id}/hitl/hitl_approval/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "report_ready"
    assert body["hitl_status"]["hitl_approval"] == "approved"


def test_reject_loops_back_and_pauses_again(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")
    session_id = _session_awaiting_approval(monkeypatch, tmp_path, sample_docs_dir)

    response = client.post(
        f"/sessions/{session_id}/hitl/hitl_approval/reject", json={"comment": "needs more detail"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["hitl_status"]["hitl_approval"] == "rejected"


def test_unknown_hitl_node_returns_404():
    response = client.post("/sessions", json={"goal": "g", "user_id": "u1"})
    session_id = response.json()["session_id"]

    response = client.post(f"/sessions/{session_id}/hitl/not_a_real_node/approve")

    assert response.status_code == 404


def test_approve_unknown_session_returns_404():
    response = client.post("/sessions/does-not-exist/hitl/hitl_approval/approve")
    assert response.status_code == 404
