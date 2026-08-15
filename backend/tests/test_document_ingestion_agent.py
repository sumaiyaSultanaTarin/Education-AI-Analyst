import pytest

from agents.document_ingestion_agent import DocumentIngestionAgent
from graph.state import new_state


def _doc(sample_docs_dir, filename, doc_type):
    return {
        "document_id": f"doc-{filename}",
        "filename": filename,
        "type": doc_type,
        "path": str(sample_docs_dir / filename),
    }


@pytest.mark.parametrize(
    "filename,doc_type",
    [
        ("course_syllabus.pdf", "pdf"),
        ("department_report.docx", "docx"),
        ("enrollment_results.xlsx", "xlsx"),
    ],
)
def test_ingest_supported_formats(sample_docs_dir, filename, doc_type):
    state = new_state(session_id="s1", goal="test ingestion")
    agent = DocumentIngestionAgent()

    state = agent.ingest(state, _doc(sample_docs_dir, filename, doc_type))

    doc_id = f"doc-{filename}"
    assert doc_id in state["agent_outputs"][agent.name]
    assert len(state["messages"]) == 1
    assert state["errors"] == []


def test_ingest_missing_file_records_error(sample_docs_dir):
    state = new_state(session_id="s1", goal="test ingestion")
    agent = DocumentIngestionAgent()
    doc = _doc(sample_docs_dir, "does_not_exist.pdf", "pdf")

    state = agent.ingest(state, doc)

    assert state["agent_outputs"] == {}
    assert len(state["errors"]) == 1
    assert "does_not_exist.pdf" in state["errors"][0]["message"]


def test_ingest_image_type_is_rejected(sample_docs_dir):
    state = new_state(session_id="s1", goal="test ingestion")
    agent = DocumentIngestionAgent()
    doc = _doc(sample_docs_dir, "scanned_result_sheet.png", "image")

    with pytest.raises(ValueError, match="vision_ocr"):
        agent.ingest(state, doc)
