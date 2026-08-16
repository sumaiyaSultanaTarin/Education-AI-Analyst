"""CSV-import fallback for Facebook post/comment data.

Used when the real Graph API integration (tools/fb_graph_api_tools.py,
not yet built) isn't available — keeps the Social Intelligence Agent
demoable without Meta app review. Expected columns, one row per comment:
fb_post_id, post_content, posted_at, fb_comment_id, author, comment_content.
"""

import csv


def parse_social_csv(path: str) -> dict:
    """Group flat post+comment CSV rows into one entry per post.

    Returns {"posts": [{"fb_post_id", "content", "posted_at", "comments": [
        {"fb_comment_id", "author", "content"}, ...
    ]}, ...]}.
    """
    posts: dict[str, dict] = {}

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            post_id = row["fb_post_id"]
            post = posts.setdefault(post_id, {
                "fb_post_id": post_id,
                "content": row["post_content"],
                "posted_at": row["posted_at"],
                "comments": [],
            })
            post["comments"].append({
                "fb_comment_id": row["fb_comment_id"],
                "author": row["author"],
                "content": row["comment_content"],
            })

    return {"posts": list(posts.values())}
