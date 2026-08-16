"""LangGraph wiring for the analysis -> report -> QA -> human-approval
pipeline (Phase 3 + Phase 5, see docs/architecture.md §5 mermaid diagram).

Runs *after* the document intake loop in graph/graph_builder.py has already
populated state["agent_outputs"] for every document — this graph doesn't
touch ingestion at all, so it's built and compiled separately rather than
folded into build_graph() there.

Unlike that intake loop, this graph is compiled with a checkpointer: the
hitl_approval node genuinely pauses execution with interrupt() until a later
API call resumes it (see api/routes/hitl.py), and LangGraph needs a
checkpointer to persist state across that pause.
"""

from datetime import datetime, timezone
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from agents.data_analyst_agent import DataAnalystAgent
from agents.knowledge_rag_agent import KnowledgeRAGAgent
from agents.qa_critic_agent import QACriticAgent
from agents.report_generator_agent import ReportGeneratorAgent
from graph.state import AnalystState


def _route_from_qa(state: AnalystState) -> Literal["report_generator", "hitl_approval"]:
    qa = state["agent_outputs"].get(QACriticAgent.name, {})
    return "hitl_approval" if qa.get("status") == "pass" else "report_generator"


def _route_from_hitl(state: AnalystState) -> str:
    # Both "rejected" and "retry" loop back to report_generator; only
    # "approved" ends the run (see docs/architecture.md §5: HITL -> approved
    # -> Finalize, HITL -> rejected/edit requested -> ReportGen).
    return END if state["hitl_status"].get("hitl_approval") == "approved" else "report_generator"


def build_report_graph(
    data_analyst_agent: DataAnalystAgent | None = None,
    rag_agent: KnowledgeRAGAgent | None = None,
    report_generator_agent: ReportGeneratorAgent | None = None,
    qa_critic_agent: QACriticAgent | None = None,
    checkpointer: MemorySaver | None = None,
) -> CompiledStateGraph:
    """Compile data_analyst -> knowledge_rag -> report_generator -> qa_critic
    -> hitl_approval, looping qa_critic/hitl_approval back to
    report_generator until QA passes and a human approves.

    Agents are injectable so tests don't have to go through a real Chroma
    disk store, the real embedding model, or a real OpenRouter client.
    """
    data_analyst = data_analyst_agent or DataAnalystAgent()
    rag = rag_agent or KnowledgeRAGAgent()
    report_generator = report_generator_agent or ReportGeneratorAgent(rag_agent=rag)
    qa_critic = qa_critic_agent or QACriticAgent()

    def _data_analyst_node(state: AnalystState) -> AnalystState:
        return data_analyst.analyze_all(state)

    def _knowledge_rag_node(state: AnalystState) -> AnalystState:
        return rag.index_all(state)

    def _report_generator_node(state: AnalystState) -> AnalystState:
        return report_generator.generate(state)

    def _qa_critic_node(state: AnalystState) -> AnalystState:
        return qa_critic.review(state)

    def _hitl_approval_node(state: AnalystState) -> AnalystState:
        report = state["agent_outputs"].get(ReportGeneratorAgent.name, {}).get("report", {})
        qa = state["agent_outputs"].get(QACriticAgent.name, {})

        decision = interrupt({
            "type": "report_approval",
            "report_path": report.get("path"),
            "qa_status": qa.get("status"),
            "qa_feedback": qa.get("feedback"),
        })
        action = decision.get("action", "rejected") if isinstance(decision, dict) else "rejected"

        state["hitl_status"]["hitl_approval"] = action
        state["messages"].append({
            "from_agent": "human",
            "to_agent": "supervisor",
            "content": f"HITL decision: {action}"
            + (f" — {decision['comment']}" if isinstance(decision, dict) and decision.get("comment") else ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return state

    graph = StateGraph(AnalystState)
    graph.add_node("data_analyst", _data_analyst_node)
    graph.add_node("knowledge_rag", _knowledge_rag_node)
    graph.add_node("report_generator", _report_generator_node)
    graph.add_node("qa_critic", _qa_critic_node)
    graph.add_node("hitl_approval", _hitl_approval_node)

    graph.set_entry_point("data_analyst")
    graph.add_edge("data_analyst", "knowledge_rag")
    graph.add_edge("knowledge_rag", "report_generator")
    graph.add_edge("report_generator", "qa_critic")
    graph.add_conditional_edges(
        "qa_critic",
        _route_from_qa,
        {"report_generator": "report_generator", "hitl_approval": "hitl_approval"},
    )
    graph.add_conditional_edges(
        "hitl_approval", _route_from_hitl, {"report_generator": "report_generator", END: END}
    )

    return graph.compile(checkpointer=checkpointer or MemorySaver())
