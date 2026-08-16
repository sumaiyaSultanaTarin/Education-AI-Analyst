from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_get_messages_returns_supervisor_message_after_create():
    session_id = client.post("/sessions", json={"goal": "test", "user_id": "u1"}).json()["session_id"]

    response = client.get(f"/sessions/{session_id}/messages")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["from_agent"] == "supervisor"


def test_get_messages_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/messages")
    assert response.status_code == 404
