from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create_session():
    response = client.post("/sessions", json={"goal": "check observability", "user_id": "u1"})
    return response.json()["session_id"]


def test_get_messages_returns_supervisor_stub_message():
    session_id = _create_session()

    response = client.get(f"/sessions/{session_id}/messages")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["from_agent"] == "supervisor"


def test_get_messages_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/messages")
    assert response.status_code == 404


def test_get_graph_returns_mermaid_for_both_graphs():
    session_id = _create_session()

    response = client.get(f"/sessions/{session_id}/graph")

    assert response.status_code == 200
    body = response.json()
    assert "intake" in body and "report" in body
    assert "supervisor" in body["intake"]
    assert "qa_critic" in body["report"]


def test_get_graph_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/graph")
    assert response.status_code == 404


def test_get_cost_with_no_llm_calls_yet_is_all_zero():
    session_id = _create_session()

    response = client.get(f"/sessions/{session_id}/cost")

    assert response.status_code == 200
    body = response.json()
    assert body["token_usage"] == {}
    assert body["total_tokens_in"] == 0
    assert body["total_tokens_out"] == 0
    assert body["total_cost_usd"] == 0


def test_get_cost_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/cost")
    assert response.status_code == 404
