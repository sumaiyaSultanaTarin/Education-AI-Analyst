from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create_session() -> str:
    response = client.post("/sessions", json={"goal": "test run", "user_id": "u1"})
    return response.json()["session_id"]


def _upload(monkeypatch, tmp_path, session_id, sample_docs_dir, filename, content_type):
    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)
    with open(sample_docs_dir / filename, "rb") as f:
        response = client.post(
            f"/sessions/{session_id}/documents",
            files={"file": (filename, f, content_type)},
        )
    assert response.status_code == 200


def test_run_processes_uploaded_documents(monkeypatch, tmp_path, sample_docs_dir):
    session_id = _create_session()
    _upload(
        monkeypatch, tmp_path, session_id, sample_docs_dir,
        "course_syllabus.pdf", "application/pdf",
    )
    _upload(
        monkeypatch, tmp_path, session_id, sample_docs_dir,
        "enrollment_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    response = client.post(f"/sessions/{session_id}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["agent_outputs"]["document_ingestion"]) == 2
    assert body["errors"] == []


def test_run_with_no_documents_completes_trivially():
    session_id = _create_session()

    response = client.post(f"/sessions/{session_id}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["agent_outputs"] == {}


def test_run_unknown_session_returns_404():
    response = client.post("/sessions/does-not-exist/run")
    assert response.status_code == 404
