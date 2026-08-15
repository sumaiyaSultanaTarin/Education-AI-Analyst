from agents.vision_ocr_agent import VisionOCRAgent
from graph.graph_builder import build_graph
from graph.state import new_state


class _FakeLLMClient:
    def chat_with_image(self, image_bytes, mime_type, prompt):
        return "RESULT SHEET - Spring 2025"


def _doc(sample_docs_dir, filename, doc_type):
    return {
        "document_id": f"doc-{filename}",
        "filename": filename,
        "type": doc_type,
        "path": str(sample_docs_dir / filename),
    }


def test_graph_processes_every_document_and_routes_by_type(sample_docs_dir):
    graph = build_graph(vision_ocr_agent=VisionOCRAgent(llm_client=_FakeLLMClient()))

    state = new_state(session_id="s1", goal="ingest everything")
    state["documents"] = [
        _doc(sample_docs_dir, "course_syllabus.pdf", "pdf"),
        _doc(sample_docs_dir, "enrollment_results.xlsx", "xlsx"),
        _doc(sample_docs_dir, "scanned_result_sheet.png", "image"),
    ]

    result = graph.invoke(state)

    assert "doc-course_syllabus.pdf" in result["agent_outputs"]["document_ingestion"]
    assert "doc-enrollment_results.xlsx" in result["agent_outputs"]["document_ingestion"]
    assert "doc-scanned_result_sheet.png" in result["agent_outputs"]["vision_ocr"]
    assert result["errors"] == []
    assert result["current_document_id"] is None


def test_graph_records_error_and_keeps_processing_other_documents(sample_docs_dir):
    graph = build_graph(vision_ocr_agent=VisionOCRAgent(llm_client=_FakeLLMClient()))

    state = new_state(session_id="s1", goal="ingest with one bad file")
    state["documents"] = [
        _doc(sample_docs_dir, "does_not_exist.pdf", "pdf"),
        _doc(sample_docs_dir, "enrollment_results.xlsx", "xlsx"),
    ]

    result = graph.invoke(state)

    assert len(result["errors"]) == 1
    assert result["errors"][0]["document_id"] == "doc-does_not_exist.pdf"
    assert "doc-enrollment_results.xlsx" in result["agent_outputs"]["document_ingestion"]


def test_graph_with_no_documents_ends_immediately():
    graph = build_graph()
    state = new_state(session_id="s1", goal="nothing to do")

    result = graph.invoke(state)

    assert result["agent_outputs"] == {}
    assert result["errors"] == []
