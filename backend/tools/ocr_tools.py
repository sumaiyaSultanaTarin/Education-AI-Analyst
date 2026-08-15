"""Image-to-text extraction, used by the Vision/OCR Agent.

Uses a vision-capable OpenRouter model through backend/core/llm_client.py
rather than a dedicated OCR engine (e.g. Tesseract) — keeps every LLM call in
the project going through the same client/fallback path, and avoids every
teammate needing to install a separate OS-level OCR binary.
"""

import mimetypes
from pathlib import Path

from core.llm_client import LLMClient, get_llm_client

_OCR_PROMPT = (
    "Transcribe all text visible in this image exactly as written, including "
    "numbers and table-like layouts. Output only the transcribed text, no "
    "commentary."
)


def extract_text_from_image(path: str, llm_client: LLMClient | None = None) -> str:
    """Read an image file and return the text a vision model transcribes from it."""
    client = llm_client or get_llm_client()
    image_bytes = Path(path).read_bytes()
    mime_type = mimetypes.guess_type(path)[0] or "image/png"
    return client.chat_with_image(image_bytes, mime_type, _OCR_PROMPT)
