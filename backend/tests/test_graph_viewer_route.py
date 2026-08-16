from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_get_graph_definition_returns_mermaid_and_nodes():
    session_id = client.post("/sessions", json={"goal": "test", "user_id": "u1"}).json()["session_id"]

    response = client.get(f"/sessions/{session_id}/graph")

    assert response.status_code == 200
    body = response.json()
    assert "graph TD" in body["mermaid"]
    assert any(node["id"] == "hitl_approval" for node in body["nodes"])
    assert any(edge["from"] == "qa_critic" and edge["to"] == "hitl_approval" for edge in body["edges"])


def test_get_graph_definition_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist/graph")
    assert response.status_code == 404
