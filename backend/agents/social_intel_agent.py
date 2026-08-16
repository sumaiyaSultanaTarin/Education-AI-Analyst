"""Social Intelligence Agent — FB post/comment data to sentiment signal.

CSV-import fallback path only for now (Phase 4). The real Graph API path
(tools/fb_graph_api_tools.py) needs a registered Meta app, page-admin
permissions, and possibly app review — tracked separately, not blocking
this agent's usefulness for the demo.
"""

from datetime import datetime, timezone

from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
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
            state["errors"].append({
                "agent_name": self.name,
                "document_id": document["document_id"],
                "error_type": type(exc).__name__,
                "message": f"{document['filename']}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        for post in parsed["posts"]:
            for comment in post["comments"]:
                comment["sentiment"] = analyze_sentiment(comment["content"])

        state["agent_outputs"].setdefault(self.name, {})[document["document_id"]] = parsed
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Processed {document['filename']} ({len(parsed['posts'])} post(s)).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state
