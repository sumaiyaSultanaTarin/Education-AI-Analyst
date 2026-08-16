"""QA/Critic Agent — checks the Report Generator's draft against the RAG
citations that fed it, before a human ever sees it (see
docs/architecture.md §2.2). Uses the shared OpenRouter client rather than
string-matching, since "does this claim follow from the source excerpts" is
a judgment call, not something regex can verify.
"""

from datetime import datetime, timezone
from pathlib import Path

from agents.data_analyst_agent import DataAnalystAgent
from agents.report_generator_agent import ReportGeneratorAgent
from core.cost_tracker import record_usage
from core.llm_client import LLMClient, get_llm_client
from core.logging_config import get_logger
from graph.state import AnalystState

logger = get_logger(__name__)

# Caps how many report_generator -> qa_critic loops one run can take before
# we stop retrying and hand the (still-flagged) report to a human instead —
# without this a stubborn FAIL verdict could loop the graph forever.
_MAX_ATTEMPTS = 2

_CRITIC_PROMPT = (
    "You are fact-checking a report against its supporting excerpts. "
    "Supporting excerpts:\n{citations}\n\n"
    "Data analysis summary the report draws numbers from:\n{data_analysis}\n\n"
    "Reply with exactly one line: PASS if the report's likely claims are "
    "consistent with the excerpts and data above, or FAIL: <reason> if not, "
    "or if the excerpts are too thin to support any real claims."
)


class QACriticAgent:
    name = "qa_critic"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        # Resolved lazily in _llm_verdict, not here — constructing the
        # default client touches OpenRouter credentials, and this agent is
        # built as a side effect of importing api.report_pipeline (see
        # get_report_graph()), which must stay import-safe with no API key.
        self._llm_client = llm_client

    def review(self, state: AnalystState) -> AnalystState:
        report = state["agent_outputs"].get(ReportGeneratorAgent.name, {}).get("report")
        attempts = state["agent_outputs"].get(self.name, {}).get("attempts", 0) + 1

        if report is None:
            verdict, feedback = "fail", "No report was generated to review."
        elif not Path(report["path"]).exists():
            verdict, feedback = "fail", f"Report file missing at {report['path']}."
        else:
            verdict, feedback = self._llm_verdict(state, report)

        forced_pass = verdict == "fail" and attempts >= _MAX_ATTEMPTS
        state["agent_outputs"][self.name] = {
            "status": "pass" if verdict == "pass" or forced_pass else "fail",
            "feedback": feedback,
            "attempts": attempts,
            "forced": forced_pass,
        }
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": (
                f"QA {'passed' if verdict == 'pass' else 'flagged issues'} "
                f"(attempt {attempts}): {feedback}"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state

    def _llm_verdict(self, state: AnalystState, report: dict) -> tuple[str, str]:
        data_analysis = state["agent_outputs"].get(DataAnalystAgent.name, {})
        citation_text = "\n".join(
            f"- [{c['filename']}] {c['text'][:200]}" for c in report.get("citations", [])
        )
        prompt = _CRITIC_PROMPT.format(
            citations=citation_text or "none", data_analysis=data_analysis or "none"
        )

        try:
            # get_llm_client() itself can raise (e.g. no API key configured),
            # so it has to stay inside this try too — this whole method must
            # degrade to a "pass through unchecked" verdict, never an
            # uncaught exception out of review().
            client = self._llm_client or get_llm_client()
            reply = client.chat([{"role": "user", "content": prompt}]).strip()
        except Exception as exc:  # noqa: BLE001 - a critic outage shouldn't block the run
            logger.error("QA critic LLM call failed: %s", exc)
            return "pass", f"Critic LLM call failed ({exc}); passed through unchecked."

        # Only reached on success — get_last_usage() reflects whatever
        # _call_model() last succeeded at, so recording it here (not in a
        # finally) avoids misattributing a stale prior call's usage to this
        # one when chat() raises above.
        record_usage(state, self.name, client.get_last_usage())

        if reply.upper().startswith("PASS"):
            return "pass", reply
        return "fail", reply
