from agents.vision_ocr_agent import VisionOCRAgent
from graph.graph_builder import build_graph
from graph.state import new_state


class _FakeLLMClient:
    def chat_with_image(self, image_bytes, mime_type, prompt):
        return "RESULT SHEET - Spring 2025"

    def get_last_usage(self):
        return None


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


def test_graph_routes_social_csv_to_social_intelligence(sample_docs_dir, tmp_path):
    csv_path = tmp_path / "comments.csv"
    csv_path.write_text(
        "fb_post_id,post_content,posted_at,fb_comment_id,author,comment_content\n"
        "post-1,Great turnout!,2025-09-01,c-1,Ayesha,Loved it!\n",
        encoding="utf-8",
    )
    graph = build_graph(vision_ocr_agent=VisionOCRAgent(llm_client=_FakeLLMClient()))

    state = new_state(session_id="s1", goal="mixed intake")
    state["documents"] = [
        _doc(sample_docs_dir, "course_syllabus.pdf", "pdf"),
        {
            "document_id": "doc-comments.csv",
            "filename": "comments.csv",
            "type": "social_csv",
            "path": str(csv_path),
        },
    ]

    result = graph.invoke(state)

    assert "doc-course_syllabus.pdf" in result["agent_outputs"]["document_ingestion"]
    output = result["agent_outputs"]["social_intelligence"]["doc-comments.csv"]
    assert output["posts"][0]["comments"][0]["sentiment"]["label"] == "positive"
    assert result["errors"] == []
