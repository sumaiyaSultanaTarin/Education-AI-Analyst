"""Facebook Graph API — real post/comment retrieval for a Page you admin.

The Phase 4 hard task (docs/final-task-assignment.md). Requires a Page
Access Token (Graph API Explorer: select your app -> your Page -> request
pages_show_list + pages_read_engagement -> Generate Access Token, or read
it off GET /me/accounts). Only works for Pages you administer — that's a
Meta restriction, not a limitation of this code, and it means no App Review
is needed for your own Page's data.

Normalizes to the exact same shape as tools/social_csv_tools.parse_social_csv
returns, so agents/social_intel_agent.py's process_csv() and process_graph_api()
can share downstream handling (sentiment scoring, etc.) unchanged.
"""

import httpx

from core.config import get_settings

_BASE_URL = "https://graph.facebook.com"


class FacebookGraphAPIError(RuntimeError):
    """Raised on any Graph API failure — missing token, bad page id, rate
    limit, network error. Caller (social_intel_agent.py) converts this to an
    ErrorRecord rather than letting it crash the run, same as every other
    agent's external-call failure handling."""


def _paginate(client: httpx.Client, path: str, params: dict) -> list[dict]:
    """Follows Graph API cursor pagination (response["paging"]["next"])
    until exhausted. Every /posts and /comments response is shaped
    {"data": [...], "paging": {"next": "<url>"}} — "next" is absent on the
    last page.
    """
    items: list[dict] = []
    url = f"{_BASE_URL}/{path}"
    while url:
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FacebookGraphAPIError(f"Graph API request to {path!r} failed: {exc}") from exc

        body = response.json()
        if "error" in body:
            raise FacebookGraphAPIError(f"Graph API error for {path!r}: {body['error']}")

        items.extend(body.get("data", []))
        url = body.get("paging", {}).get("next")
        params = None  # "next" is already a full URL with params baked in
    return items


def fetch_page_posts_and_comments(
    page_id: str | None = None,
    access_token: str | None = None,
    api_version: str | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Fetch every post on `page_id` plus every comment on each post.

    Returns {"posts": [{"fb_post_id", "content", "posted_at", "comments": [
        {"fb_comment_id", "author", "content"}, ...
    ]}, ...]} — identical shape to social_csv_tools.parse_social_csv, so
    agents/social_intel_agent.py can run the same sentiment step on either.

    page_id/access_token/api_version default to Settings (core/config.py) so
    the caller doesn't have to thread config through by hand; the explicit
    params exist so tests can inject fake values without touching env vars.
    """
    settings = get_settings()
    page_id = page_id or settings.fb_page_id
    access_token = access_token or settings.fb_page_access_token
    api_version = api_version or settings.fb_api_version

    if not access_token or not page_id:
        raise FacebookGraphAPIError(
            "FB_PAGE_ACCESS_TOKEN and FB_PAGE_ID must both be set — see .env.example."
        )

    owns_client = client is None
    client = client or httpx.Client(base_url="", timeout=30.0)
    try:
        raw_posts = _paginate(
            client,
            f"{api_version}/{page_id}/posts",
            {"fields": "id,message,created_time", "access_token": access_token},
        )

        posts = []
        for raw_post in raw_posts:
            raw_comments = _paginate(
                client,
                f"{api_version}/{raw_post['id']}/comments",
                {"fields": "id,from,message,created_time", "access_token": access_token},
            )
            posts.append({
                "fb_post_id": raw_post["id"],
                "content": raw_post.get("message", ""),
                "posted_at": raw_post.get("created_time", ""),
                "comments": [
                    {
                        "fb_comment_id": c["id"],
                        "author": c.get("from", {}).get("name", "unknown"),
                        "content": c.get("message", ""),
                    }
                    for c in raw_comments
                ],
            })
        return {"posts": posts}
    finally:
        if owns_client:
            client.close()
