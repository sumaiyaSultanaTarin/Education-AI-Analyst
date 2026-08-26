import pytest

from agents.vision_ocr_agent import VisionOCRAgent
from graph.state import new_state


class _FakeLLMClient:
    def chat_with_image(self, image_bytes, mime_type, prompt):
        return "Attendance Note - Week 6"

    def get_last_usage(self):
        return None


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


def test_process_image_records_token_usage_when_client_reports_it(sample_docs_dir):
    class _MeteredLLMClient:
        _usage = {"model": "fake/vision-model", "tokens_in": 200, "tokens_out": 15, "cost_usd": 0.0}

        def chat_with_image(self, image_bytes, mime_type, prompt):
            return "Attendance Note - Week 6"

        def get_last_usage(self):
            return self._usage

    state = new_state(session_id="s1", goal="test ocr")
    agent = VisionOCRAgent(llm_client=_MeteredLLMClient())
    doc = _doc(sample_docs_dir, "scanned_attendance_note.png")

    state = agent.process_image(state, doc)

    assert len(state["token_usage"]) == 1
    assert list(state["token_usage"].values())[0] == _MeteredLLMClient._usage


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


def test_process_image_records_error_when_no_llm_client_configured(sample_docs_dir, monkeypatch):
    """Regression test: get_llm_client() itself can raise (e.g. no
    OPENROUTER_API_KEY set) — that must become an ErrorRecord like any other
    OCR failure, not propagate out of process_image()."""

    def _broken_get_llm_client():
        raise RuntimeError("no OPENROUTER_API_KEY configured")

    monkeypatch.setattr("agents.vision_ocr_agent.get_llm_client", _broken_get_llm_client)

    state = new_state(session_id="s1", goal="test ocr")
    agent = VisionOCRAgent(llm_client=None)
    doc = _doc(sample_docs_dir, "scanned_attendance_note.png")

    state = agent.process_image(state, doc)

    assert state["agent_outputs"] == {}
    assert len(state["errors"]) == 1
    assert state["token_usage"] == {}
