from agents.report_generator_agent import ReportGeneratorAgent
from graph.state import new_state


class _FakeRAGAgent:
    def __init__(self, hits):
        self._hits = hits

    def query(self, query, n_results=5, allowed_document_ids=None):
        return self._hits


def test_generate_writes_report_and_records_citations(tmp_path):
    hits = [{"filename": "results.xlsx", "document_id": "doc-1", "chunk_index": 0, "text": "excerpt"}]
    agent = ReportGeneratorAgent(rag_agent=_FakeRAGAgent(hits), reports_dir=tmp_path)
    state = new_state(session_id="s1", goal="summarize term")
    state["documents"] = [
        {"document_id": "doc-1", "filename": "results.xlsx", "type": "xlsx", "path": "unused"}
    ]

    state = agent.generate(state)

    report = state["agent_outputs"]["report_generator"]["report"]
    assert (tmp_path / "s1" / "report.docx").exists()
    assert report["citation_count"] == 1
    assert report["citations"] == hits
    assert len(state["messages"]) == 1


def test_generate_records_error_on_failure(tmp_path, monkeypatch):
    agent = ReportGeneratorAgent(rag_agent=_FakeRAGAgent([]), reports_dir=tmp_path)
    state = new_state(session_id="s1", goal="test")

    def _boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("agents.report_generator_agent.build_report_docx", _boom)

    state = agent.generate(state)

    assert len(state["errors"]) == 1
    assert state["errors"][0]["agent_name"] == "report_generator"
    assert "report_generator" not in state["agent_outputs"]
