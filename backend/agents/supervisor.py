"""Supervisor agent — stub.

Phase 1 scope only: accept a goal and produce a placeholder single-step plan
so the state shape and API contract are exercisable end to end. Real routing
(conditional edges to the 7 worker agents, result aggregation, interrupt()
for HITL) lands once those agents exist.
"""

from datetime import datetime, timezone

from core.logging_config import get_logger
from graph.state import AnalystState, TaskStep

logger = get_logger(__name__)


class SupervisorAgent:
    name = "supervisor"

    def create_plan(self, state: AnalystState) -> AnalystState:
        logger.info("Supervisor received goal for session %s", state["session_id"])

        placeholder_step: TaskStep = {
            "step_id": "step-1",
            "agent": "unassigned",
            "description": f"Plan goal: {state['goal']}",
            "status": "pending",
            "depends_on": [],
        }
        state["plan"] = [placeholder_step]
        state["messages"].append(
            {
                "from_agent": self.name,
                "to_agent": self.name,
                "content": "Received goal, produced placeholder plan (Phase 1 stub).",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return state
