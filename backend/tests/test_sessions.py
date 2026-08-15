from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_session():
    create_response = client.post(
        "/sessions", json={"goal": "Analyze Q3 results", "user_id": "user-1"}
    )
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["goal"] == "Analyze Q3 results"
    assert body["status"] == "planned"
    assert len(body["plan"]) == 1

    session_id = body["session_id"]
    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id


def test_get_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404
