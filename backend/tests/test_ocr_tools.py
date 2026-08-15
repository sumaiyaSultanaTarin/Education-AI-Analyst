from tools.ocr_tools import extract_text_from_image


class _FakeLLMClient:
    def __init__(self):
        self.calls = []

    def chat_with_image(self, image_bytes, mime_type, prompt):
        self.calls.append((image_bytes, mime_type, prompt))
        return "RESULT SHEET - Spring 2025"


def test_extract_text_from_image_calls_vision_model(sample_docs_dir):
    fake_client = _FakeLLMClient()
    path = sample_docs_dir / "scanned_result_sheet.png"

    text = extract_text_from_image(str(path), llm_client=fake_client)

    assert text == "RESULT SHEET - Spring 2025"
    assert len(fake_client.calls) == 1
    image_bytes, mime_type, prompt = fake_client.calls[0]
    assert image_bytes == path.read_bytes()
    assert mime_type == "image/png"
    assert "transcribe" in prompt.lower()
