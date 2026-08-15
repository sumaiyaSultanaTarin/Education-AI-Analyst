"""OpenRouter chat client with a model fallback list.

Free-tier OpenRouter models throttle and occasionally go unavailable, so every
LLM call in this project must go through here rather than hitting OpenRouter
directly from an agent file (see CLAUDE.md conventions). Each model in
`settings.openrouter_fallback_models` gets a few retries with backoff before
we move to the next one; only once every model has failed do we raise.
"""

import base64
from functools import lru_cache

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import Settings, get_settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class AllModelsFailedError(RuntimeError):
    """Raised when every model in the fallback list failed."""


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self._settings.openrouter_api_key,
            base_url=self._settings.openrouter_base_url,
        )

    def chat(self, messages: list[dict], **kwargs) -> str:
        """Send a chat completion request, trying each fallback model in order."""
        return self._chat_over_models(self._settings.openrouter_fallback_models, messages, **kwargs)

    def chat_with_image(
        self, image_bytes: bytes, mime_type: str, prompt: str, **kwargs
    ) -> str:
        """Send an image + prompt to a vision-capable fallback model.

        Used by the Vision/OCR agent instead of a dedicated OCR engine — keeps
        every LLM-touching call (text or vision) going through this one client.
        """
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            }
        ]
        return self._chat_over_models(
            self._settings.openrouter_vision_fallback_models, messages, **kwargs
        )

    def _chat_over_models(self, models: list[str], messages: list[dict], **kwargs) -> str:
        last_error: Exception | None = None

        for model in models:
            try:
                return self._call_model(model, messages, **kwargs)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any
                # failure (rate limit, timeout, model down) should trigger fallback.
                logger.warning("Model %s failed, trying next fallback: %s", model, exc)
                last_error = exc

        raise AllModelsFailedError(
            f"All {len(models)} fallback models failed"
        ) from last_error

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _call_model(self, model: str, messages: list[dict], **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient()
