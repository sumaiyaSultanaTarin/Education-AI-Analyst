"""In-memory session store shared across route modules.

Placeholder until Phase 3 replaces this with the real Postgres/SQLite
WorkflowSession model (docs/architecture.md §4).
"""

from dataclasses import dataclass
from typing import Literal

from graph.state import AnalystState


@dataclass
class SessionRecord:
    state: AnalystState
    created_at: str
    # "awaiting_approval"/"report_ready" added for the Phase 5 report/HITL
    # pipeline (api/report_pipeline.py) — "planned"/"completed" are Tarin's
    # existing Phase 1/2 intake states, left as-is.
    status: Literal["planned", "completed", "awaiting_approval", "report_ready"] = "planned"


sessions: dict[str, SessionRecord] = {}
