"""Data Analyst Agent — pandas-based trends/averages/pass-rates over ingested
XLSX enrollment/results data (see docs/architecture.md §2.2).

Runs after Document Ingestion has populated state["agent_outputs"] — not
part of that intake loop. See graph/report_graph_builder.py for wiring.
"""

from datetime import datetime, timezone

from agents.document_ingestion_agent import DocumentIngestionAgent
from core.logging_config import get_logger
from graph.state import AnalystState, DocumentRef
from tools.data_analysis_tools import sheets_to_dataframes, summarize_numeric_columns
from tools.web_search_tools import search_web

logger = get_logger(__name__)


class DataAnalystAgent:
    name = "data_analyst"

    def analyze(self, state: AnalystState, document: DocumentRef) -> AnalystState:
        if document["type"] != "xlsx":
            raise ValueError(
                f"data_analyst only handles type='xlsx', got {document['type']!r}"
            )

        content = state["agent_outputs"].get(DocumentIngestionAgent.name, {}).get(
            document["document_id"]
        )
        if content is None:
            return state  # ingestion failed earlier for this document — nothing to analyze

        try:
            dataframes = sheets_to_dataframes(content["sheets"])
            summary = {
                sheet_name: summarize_numeric_columns(df)
                for sheet_name, df in dataframes.items()
            }
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.error("Failed to analyze %s: %s", document["filename"], exc)
            state["errors"].append({
                "agent_name": self.name,
                "document_id": document["document_id"],
                "error_type": type(exc).__name__,
                "message": f"{document['filename']}: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["agent_outputs"].setdefault(self.name, {})[document["document_id"]] = summary
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Analyzed {document['filename']} ({len(dataframes)} sheet(s)).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state

    def analyze_all(self, state: AnalystState) -> AnalystState:
        """Analyze every xlsx document in state["documents"], then add one
        web-search pass for external benchmark context — used as a
        report-graph node.
        """
        for document in state["documents"]:
            if document["type"] == "xlsx":
                state = self.analyze(state, document)
        return self._add_web_context(state)

    def _add_web_context(self, state: AnalystState) -> AnalystState:
        """One search for benchmark context relevant to state["goal"] — not
        per-document, since the goal (not any single file) is what frames
        what's worth benchmarking against. No-ops (records an ErrorRecord,
        doesn't raise) when TAVILY_API_KEY isn't configured — same
        degrade-gracefully pattern as every other optional external call.
        """
        try:
            results = search_web(f"{state['goal']} benchmark statistics")
        except Exception as exc:  # noqa: BLE001 - convert to ErrorRecord, don't crash the run
            logger.warning("Web search context skipped: %s", exc)
            state["errors"].append({
                "agent_name": self.name,
                "document_id": None,
                "error_type": type(exc).__name__,
                "message": f"Web search context: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return state

        state["agent_outputs"].setdefault(self.name, {})["web_context"] = results
        state["messages"].append({
            "from_agent": self.name,
            "to_agent": "supervisor",
            "content": f"Found {len(results)} external benchmark result(s) for context.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state
