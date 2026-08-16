from fastapi.testclient import TestClient

from api.main import app
from api.session_store import sessions

client = TestClient(app)


def test_get_cost_returns_zeroed_breakdown_for_a_fresh_session():
    session_id = client.post("/sessions", json={"goal": "test", "user_id": "u1"}).json()["session_id"]

    response = client.get(f"/sessions/{session_id}/cost")

    assert response.status_code == 200
    body = response.json()
    assert body["by_agent_model"] == {}
    assert body["total_tokens_in"] == 0
    assert body["total_cost_usd"] == 0.0


def test_get_cost_aggregates_recorded_usage():
    session_id = client.post("/sessions", json={"goal": "test", "user_id": "u1"}).json()["session_id"]
    sessions[session_id].state["token_usage"] = {
        "qa_critic:m1:free": {"model": "m1:free", "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.0},
        "vision_ocr:m2:free": {"model": "m2:free", "tokens_in": 50, "tokens_out": 10, "cost_usd": 0.0},
    }

    response = client.get(f"/sessions/{session_id}/cost")

    body = response.json()
    assert body["total_tokens_in"] == 150
    assert body["total_tokens_out"] == 30
    assert len(body["by_agent_model"]) == 2


def test_get_cost_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/cost")
    assert response.status_code == 404
