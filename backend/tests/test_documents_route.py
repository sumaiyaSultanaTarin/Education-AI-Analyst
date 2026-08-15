from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create_session() -> str:
    response = client.post("/sessions", json={"goal": "test upload", "user_id": "u1"})
    return response.json()["session_id"]


def test_upload_pdf(monkeypatch, tmp_path, sample_docs_dir):
    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)
    session_id = _create_session()

    with open(sample_docs_dir / "course_syllabus.pdf", "rb") as f:
        response = client.post(
            f"/sessions/{session_id}/documents",
            files={"file": ("course_syllabus.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "course_syllabus.pdf"
    assert body["type"] == "pdf"

    session = client.get(f"/sessions/{session_id}").json()
    assert len(session["documents"]) == 1
    assert session["documents"][0]["document_id"] == body["document_id"]


def test_upload_unsupported_extension_returns_400(monkeypatch, tmp_path):
    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)
    session_id = _create_session()

    response = client.post(
        f"/sessions/{session_id}/documents",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_to_unknown_session_returns_404(monkeypatch, tmp_path):
    monkeypatch.setattr("api.routes.documents._UPLOAD_DIR", tmp_path)

    response = client.post(
        "/sessions/does-not-exist/documents",
        files={"file": ("course_syllabus.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 404
