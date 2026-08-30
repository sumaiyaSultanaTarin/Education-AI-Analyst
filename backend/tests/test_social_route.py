"""Tests for `/sessions/{id}/social/pull-facebook`.

Mocks agents.social_intel_agent.fetch_page_posts_and_comments — no real
Facebook call, no real FB_PAGE_ACCESS_TOKEN needed to run this suite, same
reasoning as conftest.py's _no_real_web_search fixture for Tavily.
"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create_session():
    response = client.post("/sessions", json={"goal": "check social pull", "user_id": "u1"})
    return response.json()["session_id"]


def test_pull_facebook_returns_posts(monkeypatch):
    def _fake_fetch(**kwargs):
        return {
            "posts": [{
                "fb_post_id": "p1",
                "content": "Welcome back!",
                "posted_at": "2026-08-01",
                "comments": [{"fb_comment_id": "c1", "author": "Alex", "content": "Great!"}],
            }]
        }

    monkeypatch.setattr("agents.social_intel_agent.fetch_page_posts_and_comments", _fake_fetch)
    session_id = _create_session()

    response = client.post(f"/sessions/{session_id}/social/pull-facebook")

    assert response.status_code == 200
    body = response.json()
    assert body["posts_found"] == 1
    assert body["posts"][0]["comments"][0]["sentiment"]["label"]
    assert body["errors"] == []


def test_pull_facebook_returns_error_when_credentials_missing(monkeypatch):
    from tools.fb_graph_api_tools import FacebookGraphAPIError

    def _fake_fetch(**kwargs):
        raise FacebookGraphAPIError("FB_PAGE_ACCESS_TOKEN and FB_PAGE_ID must both be set")

    monkeypatch.setattr("agents.social_intel_agent.fetch_page_posts_and_comments", _fake_fetch)
    session_id = _create_session()

    response = client.post(f"/sessions/{session_id}/social/pull-facebook")

    assert response.status_code == 200
    body = response.json()
    assert body["posts_found"] == 0
    assert len(body["errors"]) == 1


def test_pull_facebook_unknown_session_returns_404():
    response = client.post("/sessions/does-not-exist/social/pull-facebook")
    assert response.status_code == 404
