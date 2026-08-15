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
    status: Literal["planned", "completed"] = "planned"


sessions: dict[str, SessionRecord] = {}
