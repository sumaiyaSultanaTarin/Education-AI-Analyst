import pytest

from agents.social_intel_agent import SocialIntelligenceAgent
from graph.state import new_state

_CSV_HEADER = "fb_post_id,post_content,posted_at,fb_comment_id,author,comment_content\n"


def _write_csv(tmp_path, rows: str):
    path = tmp_path / "comments.csv"
    path.write_text(_CSV_HEADER + rows, encoding="utf-8")
    return path


def _doc(path, document_id="doc-1", doc_type="social_csv"):
    return {
        "document_id": document_id,
        "filename": path.name if hasattr(path, "name") else "comments.csv",
        "type": doc_type,
        "path": str(path),
    }


def test_process_csv_attaches_sentiment_to_every_comment(tmp_path):
    rows = (
        "post-1,Great turnout!,2025-09-01,c-1,Ayesha,Loved it - amazing event!\n"
        "post-1,Great turnout!,2025-09-01,c-2,Rahim,This was disappointing and poorly run\n"
    )
    path = _write_csv(tmp_path, rows)
    state = new_state(session_id="s1", goal="analyze comments")
    agent = SocialIntelligenceAgent()

    state = agent.process_csv(state, _doc(path))

    output = state["agent_outputs"][agent.name]["doc-1"]
    comments = output["posts"][0]["comments"]
    assert len(comments) == 2
    assert all("sentiment" in c for c in comments)
    assert all("score" in c["sentiment"] and "label" in c["sentiment"] for c in comments)
    assert state["errors"] == []
    assert len(state["messages"]) == 1


def test_process_csv_missing_file_records_error(tmp_path):
    state = new_state(session_id="s1", goal="analyze comments")
    agent = SocialIntelligenceAgent()
    doc = _doc(tmp_path / "does_not_exist.csv")

    state = agent.process_csv(state, doc)

    assert state["agent_outputs"] == {}
    assert len(state["errors"]) == 1
    assert state["errors"][0]["document_id"] == "doc-1"


def test_process_csv_rejects_non_csv_type(tmp_path):
    state = new_state(session_id="s1", goal="analyze comments")
    agent = SocialIntelligenceAgent()
    doc = _doc(tmp_path / "file.pdf", doc_type="pdf")

    with pytest.raises(ValueError, match="social_intelligence only handles"):
        agent.process_csv(state, doc)


def test_process_graph_api_attaches_sentiment_to_every_comment(monkeypatch):
    def _fake_fetch(**kwargs):
        return {
            "posts": [{
                "fb_post_id": "post-1",
                "content": "Welcome back!",
                "posted_at": "2026-08-01",
                "comments": [{"fb_comment_id": "c-1", "author": "Alex", "content": "Great news!"}],
            }]
        }

    monkeypatch.setattr("agents.social_intel_agent.fetch_page_posts_and_comments", _fake_fetch)
    state = new_state(session_id="s1", goal="analyze comments")
    agent = SocialIntelligenceAgent()

    state = agent.process_graph_api(state)

    output = state["agent_outputs"][agent.name]["graph_api"]
    assert output["posts"][0]["comments"][0]["sentiment"]["label"]
    assert state["errors"] == []
    assert len(state["messages"]) == 1


def test_process_graph_api_records_error_when_credentials_missing(monkeypatch):
    from tools.fb_graph_api_tools import FacebookGraphAPIError

    def _fake_fetch(**kwargs):
        raise FacebookGraphAPIError("FB_PAGE_ACCESS_TOKEN and FB_PAGE_ID must both be set")

    monkeypatch.setattr("agents.social_intel_agent.fetch_page_posts_and_comments", _fake_fetch)
    state = new_state(session_id="s1", goal="analyze comments")
    agent = SocialIntelligenceAgent()

    state = agent.process_graph_api(state)

    assert state["agent_outputs"] == {}
    assert len(state["errors"]) == 1
    assert state["errors"][0]["document_id"] is None
