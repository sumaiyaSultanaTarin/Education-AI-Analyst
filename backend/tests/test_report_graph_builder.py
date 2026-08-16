from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agents.knowledge_rag_agent import KnowledgeRAGAgent
from agents.qa_critic_agent import QACriticAgent
from agents.report_generator_agent import ReportGeneratorAgent
from graph.report_graph_builder import build_report_graph
from graph.state import new_state


class _FakeLLMClient:
    def __init__(self, reply="PASS"):
        self._reply = reply

    def chat(self, messages, **kwargs):
        return self._reply

    def get_last_usage(self):
        return None


def _base_state(session_id="s1"):
    state = new_state(session_id=session_id, goal="summarize term")
    state["documents"] = [
        {"document_id": "doc-1", "filename": "results.xlsx", "type": "xlsx", "path": "unused"}
    ]
    state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"sheets": {"Term1": [{"score": 80}, {"score": 20}]}}
    }
    return state


def _build_graph(tmp_path, chroma_collection, fake_embed_fn, qa_reply="PASS"):
    rag_agent = KnowledgeRAGAgent(collection=chroma_collection, embed_fn=fake_embed_fn)
    return build_report_graph(
        rag_agent=rag_agent,
        report_generator_agent=ReportGeneratorAgent(rag_agent=rag_agent, reports_dir=tmp_path),
        qa_critic_agent=QACriticAgent(llm_client=_FakeLLMClient(qa_reply)),
        checkpointer=MemorySaver(),
    )


# NOTE: the exact shape LangGraph merges into invoke()'s return value around
# an interrupt() call was not verifiable in this environment (no Python
# runtime available to run the real langgraph package) — only the documented,
# version-stable "__interrupt__" key / graph.get_state(config).next contract
# is asserted on here. Please confirm with `pytest` on a real install.
def test_report_graph_pauses_at_hitl_then_resumes_on_approval(tmp_path, chroma_collection, fake_embed_fn):
    graph = _build_graph(tmp_path, chroma_collection, fake_embed_fn)
    config = {"configurable": {"thread_id": "s1"}}

    result = graph.invoke(_base_state(), config=config)

    assert "__interrupt__" in result
    snapshot = graph.get_state(config)
    assert snapshot.next  # still paused, hasn't reached END

    resumed = graph.invoke(Command(resume={"action": "approved"}), config=config)

    assert "__interrupt__" not in resumed
    assert resumed["hitl_status"]["hitl_approval"] == "approved"
    assert resumed["agent_outputs"]["data_analyst"]["doc-1"]["Term1"]["score"]["pass_rate"] == 50.0
    assert not graph.get_state(config).next  # run has completed


def test_report_graph_loops_qa_failures_then_forces_through(tmp_path, chroma_collection, fake_embed_fn):
    graph = _build_graph(tmp_path, chroma_collection, fake_embed_fn, qa_reply="FAIL: unsupported claim")
    config = {"configurable": {"thread_id": "s2"}}

    result = graph.invoke(_base_state(session_id="s2"), config=config)

    assert "__interrupt__" in result
    assert result["agent_outputs"]["qa_critic"]["attempts"] == 2
    assert result["agent_outputs"]["qa_critic"]["forced"] is True


def test_report_graph_rejected_hitl_loops_back_to_report_generator(tmp_path, chroma_collection, fake_embed_fn):
    graph = _build_graph(tmp_path, chroma_collection, fake_embed_fn)
    config = {"configurable": {"thread_id": "s3"}}

    graph.invoke(_base_state(session_id="s3"), config=config)
    resumed = graph.invoke(
        Command(resume={"action": "rejected", "comment": "add more detail"}), config=config
    )

    # Rejected loops back through report_generator -> qa_critic -> hitl_approval
    # again, so we should be paused a second time rather than at END.
    assert "__interrupt__" in resumed
