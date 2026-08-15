import pytest

from agents.data_analyst_agent import DataAnalystAgent
from graph.state import new_state


def _xlsx_doc(document_id="doc-1", filename="enrollment_results.xlsx"):
    return {"document_id": document_id, "filename": filename, "type": "xlsx", "path": "unused"}


def test_analyze_computes_summary_from_ingested_sheets():
    agent = DataAnalystAgent()
    state = new_state(session_id="s1", goal="test")
    document = _xlsx_doc()
    state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"sheets": {"Term1": [{"score": 80}, {"score": 20}]}}
    }

    state = agent.analyze(state, document)

    summary = state["agent_outputs"]["data_analyst"]["doc-1"]
    assert summary["Term1"]["score"]["pass_rate"] == 50.0
    assert len(state["messages"]) == 1


def test_analyze_skips_when_ingestion_failed():
    agent = DataAnalystAgent()
    state = new_state(session_id="s1", goal="test")
    document = _xlsx_doc("doc-missing")

    state = agent.analyze(state, document)

    assert "data_analyst" not in state["agent_outputs"]


def test_analyze_rejects_non_xlsx_documents():
    agent = DataAnalystAgent()
    state = new_state(session_id="s1", goal="test")
    document = {"document_id": "doc-1", "filename": "a.pdf", "type": "pdf", "path": "unused"}

    with pytest.raises(ValueError):
        agent.analyze(state, document)


def test_analyze_all_only_processes_xlsx_documents():
    agent = DataAnalystAgent()
    state = new_state(session_id="s1", goal="test")
    state["documents"] = [
        _xlsx_doc("doc-1", "results.xlsx"),
        {"document_id": "doc-2", "filename": "notes.pdf", "type": "pdf", "path": "unused"},
    ]
    state["agent_outputs"]["document_ingestion"] = {
        "doc-1": {"sheets": {"Term1": [{"score": 80}]}},
        "doc-2": {"pages": []},
    }

    state = agent.analyze_all(state)

    assert set(state["agent_outputs"]["data_analyst"]) == {"doc-1"}
