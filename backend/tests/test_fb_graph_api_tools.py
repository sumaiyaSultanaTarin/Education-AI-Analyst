"""Tests for tools/fb_graph_api_tools.py.

Uses httpx.MockTransport instead of hitting the real Graph API — no network
call, no real token needed. Covers pagination (posts AND comments each get
their own paged response) and the two failure paths (missing credentials,
an error body from the API).
"""

import httpx
import pytest

from tools.fb_graph_api_tools import FacebookGraphAPIError, fetch_page_posts_and_comments

_POSTS_PAGE_1 = {
    "data": [{"id": "post-1", "message": "Welcome back!", "created_time": "2026-08-01T00:00:00+0000"}],
    "paging": {"next": "https://graph.facebook.com/v21.0/page-1/posts?after=CURSOR"},
}
_POSTS_PAGE_2 = {
    "data": [{"id": "post-2", "message": "Great parent-teacher meeting.", "created_time": "2026-08-02T00:00:00+0000"}],
    "paging": {},
}
_COMMENTS_POST_1 = {
    "data": [
        {"id": "c-1", "from": {"name": "Alex"}, "message": "Loved the update!", "created_time": "x"},
    ],
    "paging": {},
}
_COMMENTS_POST_2 = {
    "data": [
        {"id": "c-2", "from": {"name": "Sam"}, "message": "Great meeting, thanks!", "created_time": "x"},
    ],
    "paging": {},
}


def _mock_client(responses_by_path: dict[str, dict]) -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        for path, body in responses_by_path.items():
            if path in str(request.url):
                return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": {"message": "not found"}})

    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_fetch_page_posts_and_comments_paginates_posts_and_fetches_each_comment_set():
    client = _mock_client({
        # "after=CURSOR" must be checked before the plainer "page-1/posts?"
        # pattern below — both match the page-2 URL as a substring, and
        # _mock_client returns on the first match, so order is significant.
        "after=CURSOR": _POSTS_PAGE_2,
        "page-1/posts?": _POSTS_PAGE_1,
        "post-1/comments": _COMMENTS_POST_1,
        "post-2/comments": _COMMENTS_POST_2,
    })

    result = fetch_page_posts_and_comments(
        page_id="page-1", access_token="fake-token", api_version="v21.0", client=client
    )

    assert [p["fb_post_id"] for p in result["posts"]] == ["post-1", "post-2"]
    post_1 = result["posts"][0]
    assert post_1["content"] == "Welcome back!"
    assert post_1["comments"] == [
        {"fb_comment_id": "c-1", "author": "Alex", "content": "Loved the update!"}
    ]


def test_fetch_raises_when_credentials_missing(monkeypatch):
    # page_id="" / access_token="" alone aren't enough to prove this —
    # fetch_page_posts_and_comments() falls back to Settings.fb_page_id/
    # fb_page_access_token when the explicit args are falsy, so without also
    # patching get_settings() this test's outcome would depend on whether a
    # real FB_PAGE_ACCESS_TOKEN happens to be configured in .env.
    monkeypatch.setattr(
        "tools.fb_graph_api_tools.get_settings",
        lambda: type("S", (), {"fb_page_id": "", "fb_page_access_token": "", "fb_api_version": "v21.0"})(),
    )

    with pytest.raises(FacebookGraphAPIError, match="FB_PAGE_ACCESS_TOKEN"):
        fetch_page_posts_and_comments(page_id="", access_token="", client=_mock_client({}))


def test_fetch_raises_on_api_error_body():
    client = _mock_client({"page-1/posts?": {"error": {"message": "Invalid OAuth token"}}})

    with pytest.raises(FacebookGraphAPIError, match="Invalid OAuth token"):
        fetch_page_posts_and_comments(
            page_id="page-1", access_token="bad-token", api_version="v21.0", client=client
        )
