"""Social Intelligence Agent — FB post/comment data to sentiment signal.

Two input paths feeding the same downstream sentiment step: the CSV-import
fallback (tools/social_csv_tools.py, always available) and the real Graph
API path (tools/fb_graph_api_tools.py, needs FB_PAGE_ACCESS_TOKEN +
FB_PAGE_ID in .env — see that module's docstring for how to get a Page
Access Token). Both return the same {"posts": [...]} shape, so they share
_score_and_record below rather than duplicating the sentiment loop twice.
"""

from datetime import datetime, timezone

from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
from tools.fb_graph_api_tools import fetch_page_posts_and_comments
from tools.sentiment_tools import analyze_sentiment
from tools.social_csv_tools import parse_social_csv

logger = get_logger(__name__)


class SocialIntelligenceAgent:
    name = "social_intelligence"

    def process_csv(self, state: AnalystState, document: DocumentRef) -> AnalystState:
        if document["type"] != "social_csv":
            raise ValueError(
                f"social_intelligence only handles type='social_csv', got {document['type']!r}"
            )

        try:
            parsed = parse_social_csv(document["path"])
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Failed to parse social CSV %s: %s", document["filename"], exc)
            self._record_error(state, exc, document["document_id"], document["filename"])
            return state

        self._score_and_record(state, key=document["document_id"], parsed=parsed, label=document["filename"])
        return state

    def process_graph_api(self, state: AnalystState) -> AnalystState:
        """Live pull for the session's configured FB Page — not routed from
        an uploaded document (there isn't one), so callers invoke this
        directly rather than through graph/graph_builder.py's per-document
        routing.
        """
        try:
            parsed = fetch_page_posts_and_comments()
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Facebook Graph API pull failed: %s", exc)
            self._record_error(state, exc, document_id=None, label="Facebook Graph API")
            return state

        self._score_and_record(state, key="graph_api", parsed=parsed, label="Facebook Graph API")
        return state

    def _record_error(self, state, exc: Exception, document_id: str | None, label: str) -> None:
        state["errors"].append({
            "agent_name": self.name,
            "document_id": document_id,
            "error_type": type(exc).__name__,
            "message": f"{label}: {exc}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _score_and_record(self, state, key: str, parsed: dict, label: str) -> None:
        for post in parsed["posts"]:
            for comment in post["comments"]:
                comment["sentiment"] = analyze_sentiment(comment["content"])

        state["agent_outputs"].setdefault(self.name, {})[key] = parsed
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Processed {label} ({len(parsed['posts'])} post(s)).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
