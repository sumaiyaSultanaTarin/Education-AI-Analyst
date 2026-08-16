"""End-to-end integration test (Phase 7): walks the whole pipeline through
the real FastAPI app rather than testing each route/agent in isolation —
create session -> upload every document type -> run intake -> generate
report -> approve via HITL -> fetch the final file.

Only the pieces that need real external services (embeddings model, Chroma
disk store, OpenRouter) are faked, matching the pattern already used in
test_report_route.py/test_hitl_route.py; everything else (FastAPI routing,
the intake graph, the report graph, HITL interrupt/resume, session state
bookkeeping) runs for real.
"""

from pathlib import Path

from docx import Document
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

    def chat_with_image(self, image_bytes, mime_type, prompt):
        return "RESULT SHEET - transcribed text"

    def get_last_usage(self):
        return None


def _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, reports_dir):
    rag_agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    graph = build_report_graph(
        rag_agent=rag_agent,
        report_generator_agent=ReportGeneratorAgent(rag_agent=rag_agent, reports_dir=reports_dir),
        qa_critic_agent=QACriticAgent(llm_client=_FakeLLMClient()),
        checkpointer=MemorySaver(),
    )
    monkeypatch.setattr("api.report_pipeline.get_report_graph", lambda: graph)
    return graph


def _upload(monkeypatch, tmp_path, session_id, sample_docs_dir, filename, content_type):
    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)
    with open(sample_docs_dir / filename, "rb") as f:
        response = client.post(
            f"/sessions/{session_id}/documents",
            files={"file": (filename, f, content_type)},
        )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_pipeline_from_upload_to_approved_report(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")

    # 1. Create session
    create_response = client.post(
        "/sessions", json={"goal": "Summarize Spring 2025 performance", "user_id": "e2e-user"}
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]
    assert create_response.json()["status"] == "planned"

    # 2. Upload one of every document type the app supports
    _upload(monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "course_syllabus.pdf", "application/pdf")
    _upload(
        monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "department_report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    _upload(
        monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "enrollment_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    _upload(
        monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "scanned_result_sheet.png", "image/png"
    )
    _upload(
        monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "facebook_comments_sample.csv", "text/csv"
    )

    get_response = client.get(f"/sessions/{session_id}")
    assert len(get_response.json()["documents"]) == 5

    # 3. Run intake — ingests every document by type (Document Ingestion,
    # Vision/OCR, Social Intelligence agents). Vision/OCR's default agent
    # (built once at sessions.py import time) resolves its LLM client lazily
    # via tools/ocr_tools.get_llm_client() at call time — patch that, not
    # agents.vision_ocr_agent's own (unused) import of the same name.
    monkeypatch.setattr("tools.ocr_tools.get_llm_client", lambda: _FakeLLMClient())
    run_response = client.post(f"/sessions/{session_id}/run")
    assert run_response.status_code == 200, run_response.text
    run_body = run_response.json()
    assert run_body["status"] == "completed"
    assert run_body["errors"] == []
    assert set(run_body["agent_outputs"]) >= {"document_ingestion", "vision_ocr", "social_intelligence"}

    # 4. Generate the report — data_analyst -> knowledge_rag -> report_generator
    # -> qa_critic -> hitl_approval (pauses here)
    generate_response = client.post(f"/sessions/{session_id}/generate-report")
    assert generate_response.status_code == 200, generate_response.text
    generate_body = generate_response.json()
    assert generate_body["status"] == "awaiting_approval"
    assert generate_body["qa_status"] == "pass"
    assert generate_body["report_path"] is not None
    assert Path(generate_body["report_path"]).exists()

    # The uploaded CSV's sentiment data should actually make it into the
    # report (regression coverage for the report_generator_agent.py key
    # mismatch that silently dropped Social Intelligence output).
    report_doc = Document(generate_body["report_path"])
    report_text = "\n".join(p.text for p in report_doc.paragraphs)
    assert "Social Intelligence" in report_text

    # Report isn't handed out until approved
    unapproved_fetch = client.get(f"/sessions/{session_id}/report")
    assert unapproved_fetch.status_code == 404

    # 5. Approve via HITL
    approve_response = client.post(f"/sessions/{session_id}/hitl/hitl_approval/approve")
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "report_ready"
    assert approve_response.json()["hitl_status"]["hitl_approval"] == "approved"

    # 6. Fetch the final report — both formats
    final_fetch = client.get(f"/sessions/{session_id}/report")
    assert final_fetch.status_code == 200
    assert final_fetch.content  # a real .docx was written and served

    final_fetch_pptx = client.get(f"/sessions/{session_id}/report", params={"format": "pptx"})
    assert final_fetch_pptx.status_code == 200
    assert final_fetch_pptx.content

    # 7. Session status reflects the final state, no 500s along the way
    final_get = client.get(f"/sessions/{session_id}")
    assert final_get.status_code == 200
    assert final_get.json()["status"] == "report_ready"


def test_full_pipeline_reject_then_approve(
    monkeypatch, tmp_path, sample_docs_dir, chroma_collection, fake_embed_fn
):
    _install_fake_report_graph(monkeypatch, chroma_collection, fake_embed_fn, tmp_path / "reports")

    session_id = client.post(
        "/sessions", json={"goal": "test rejection loop", "user_id": "e2e-user"}
    ).json()["session_id"]
    _upload(
        monkeypatch, tmp_path / "uploads", session_id, sample_docs_dir, "enrollment_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    client.post(f"/sessions/{session_id}/run")
    client.post(f"/sessions/{session_id}/generate-report")

    reject_response = client.post(
        f"/sessions/{session_id}/hitl/hitl_approval/reject", json={"comment": "needs more detail"}
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "awaiting_approval"
    assert reject_response.json()["hitl_status"]["hitl_approval"] == "rejected"

    approve_response = client.post(f"/sessions/{session_id}/hitl/hitl_approval/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "report_ready"

    final_fetch = client.get(f"/sessions/{session_id}/report")
    assert final_fetch.status_code == 200
