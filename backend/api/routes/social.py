"""`/sessions/{id}/social/pull-facebook` — trigger a live Facebook Graph API
pull for the session's configured Page (FB_PAGE_ID/FB_PAGE_ACCESS_TOKEN in
.env), separate from the CSV-import path (routes/documents.py's upload +
routes/sessions.py's /run, for a social_csv document).

Not part of the intake graph (graph/graph_builder.py) since there's no
uploaded document to route on — this calls the agent directly, the same
way routes/report.py calls DataAnalystAgent/etc. outside a graph node.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.social_intel_agent import SocialIntelligenceAgent
from api.session_store import save_session, sessions
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["social"])

_agent = SocialIntelligenceAgent()


class SocialPullResponse(BaseModel):
    posts_found: int
    posts: list[dict]
    errors: list[dict]


@router.post("/{session_id}/social/pull-facebook", response_model=SocialPullResponse)
def pull_facebook(session_id: str) -> SocialPullResponse:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    errors_before = len(record.state["errors"])
    record.state = _agent.process_graph_api(record.state)
    save_session(session_id, record)

    new_errors = record.state["errors"][errors_before:]
    output = record.state["agent_outputs"].get(_agent.name, {}).get("graph_api", {})
    posts = output.get("posts", [])

    logger.info("Session %s: pulled %d Facebook post(s)", session_id, len(posts))
    return SocialPullResponse(posts_found=len(posts), posts=posts, errors=new_errors)
