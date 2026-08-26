"""Tests for tools/web_search_tools.py.

Uses httpx.MockTransport instead of hitting the real Tavily API — no
network call, no real key needed.
"""

import httpx
import pytest

from tools.web_search_tools import WebSearchError, search_web

_TAVILY_RESPONSE = {
    "query": "average class size primary school",
    "results": [
        {
            "title": "National average class sizes",
            "url": "https://example.org/class-sizes",
            "content": "The national average is 24 students per class.",
        },
    ],
}


def _mock_client(body: dict, status: int = 200) -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_search_web_returns_normalized_results():
    results = search_web(
        "average class size primary school", api_key="fake-key", client=_mock_client(_TAVILY_RESPONSE)
    )

    assert results == [
        {
            "title": "National average class sizes",
            "url": "https://example.org/class-sizes",
            "snippet": "The national average is 24 students per class.",
        }
    ]


def test_search_web_raises_when_api_key_missing():
    with pytest.raises(WebSearchError, match="TAVILY_API_KEY"):
        search_web("anything", api_key="", client=_mock_client(_TAVILY_RESPONSE))


def test_search_web_raises_on_unexpected_response_shape():
    with pytest.raises(WebSearchError, match="Unexpected Tavily response"):
        search_web("anything", api_key="fake-key", client=_mock_client({"error": "bad request"}))
