import pytest

from agents.vision_ocr_agent import VisionOCRAgent
from graph.state import new_state


class _FakeLLMClient:
    def chat_with_image(self, image_bytes, mime_type, prompt):
        return "Attendance Note - Week 6"


def _doc(sample_docs_dir, filename, doc_type="image"):
    return {
        "document_id": f"doc-{filename}",
        "filename": filename,
        "type": doc_type,
        "path": str(sample_docs_dir / filename),
    }


def test_process_image(sample_docs_dir):
    state = new_state(session_id="s1", goal="test ocr")
    agent = VisionOCRAgent(llm_client=_FakeLLMClient())
    doc = _doc(sample_docs_dir, "scanned_attendance_note.png")

    state = agent.process_image(state, doc)

    assert state["agent_outputs"][agent.name][doc["document_id"]] == {
        "text": "Attendance Note - Week 6"
    }
    assert len(state["messages"]) == 1
    assert state["errors"] == []


def test_process_image_missing_file_records_error(sample_docs_dir):
    state = new_state(session_id="s1", goal="test ocr")
    agent = VisionOCRAgent(llm_client=_FakeLLMClient())
    doc = _doc(sample_docs_dir, "does_not_exist.png")

    state = agent.process_image(state, doc)

    assert state["agent_outputs"] == {}
    assert len(state["errors"]) == 1


def test_process_image_rejects_non_image_type(sample_docs_dir):
    state = new_state(session_id="s1", goal="test ocr")
    agent = VisionOCRAgent(llm_client=_FakeLLMClient())
    doc = _doc(sample_docs_dir, "course_syllabus.pdf", doc_type="pdf")

    with pytest.raises(ValueError, match="vision_ocr only handles"):
        agent.process_image(state, doc)
