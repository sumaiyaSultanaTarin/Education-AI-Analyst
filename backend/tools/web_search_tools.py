"""Web search via the Tavily API — free tier key at tavily.com.

Used by the Data Analyst Agent to pull external benchmark/context results
alongside the pandas analysis of uploaded data (see agents/data_analyst_agent.py).
Tavily was chosen over a keyless scraper (e.g. DuckDuckGo HTML scraping)
because it returns clean, pre-summarized results meant for LLM consumption
rather than raw HTML needing its own parsing step.
"""

import httpx

from core.config import get_settings

_SEARCH_URL = "https://api.tavily.com/search"


class WebSearchError(RuntimeError):
    """Raised on any search failure — missing key, bad request, network
    error. Caller (agents/data_analyst_agent.py) converts this to an
    ErrorRecord rather than letting it crash the run, same pattern as every
    other agent's external-call failure handling."""


def search_web(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Search the web via Tavily. Returns [{"title", "url", "snippet"}, ...].

    api_key defaults to Settings.tavily_api_key (core/config.py) so callers
    don't have to thread config through by hand; the explicit param exists
    so tests can inject a fake key without touching env vars.
    """
    api_key = api_key or get_settings().tavily_api_key
    if not api_key:
        raise WebSearchError("TAVILY_API_KEY must be set — see .env.example.")

    owns_client = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        try:
            response = client.post(
                _SEARCH_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Tavily search for {query!r} failed: {exc}") from exc

        body = response.json()
        if "results" not in body:
            raise WebSearchError(f"Unexpected Tavily response for {query!r}: {body}")

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in body["results"]
        ]
    finally:
        if owns_client:
            client.close()
