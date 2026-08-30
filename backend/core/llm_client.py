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

# The openai SDK defaults to a 600s (10 min) timeout per call when none is
# set. Free-tier OpenRouter models occasionally hang instead of erroring, so
# without an explicit bound one stuck model can silently freeze an entire
# request for up to 10 minutes before the fallback list even gets a chance
# to try the next model. 30s is generous for a chat completion but still
# fails fast enough that _chat_over_models' fallback loop actually kicks in.
_REQUEST_TIMEOUT_SECONDS = 30.0


class AllModelsFailedError(RuntimeError):
    """Raised when every model in the fallback list failed."""


# $/1K-token estimates for cost display. Every model in
# Settings.openrouter_fallback_models is a ":free" OpenRouter model, so this
# is empty by default and every call legitimately costs $0.00 — the table
# exists so a paid model added to the fallback list later shows a real
# estimate instead of a silently wrong $0.00.
_PRICING_PER_1K_USD: dict[str, tuple[float, float]] = {}


def _estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICING_PER_1K_USD.get(model, (0.0, 0.0))
    return round((tokens_in / 1000) * price_in + (tokens_out / 1000) * price_out, 6)


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = OpenAI(
            api_key=self._settings.openrouter_api_key,
            base_url=self._settings.openrouter_base_url,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        # Usage from the most recent successful _call_model() call — read via
        # get_last_usage() right after chat()/chat_with_image() returns.
        # Not thread-safe (fine: this app makes one LLM call at a time per
        # request, same as the rest of the in-memory session store).
        self._last_usage: dict | None = None

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
        if response.usage is not None:
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            self._last_usage = {
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                # _PRICING_PER_1K_USD is empty for the ":free" fallback models,
                # so this is honestly 0.0 for them and only non-zero if a paid
                # model is ever added to a fallback list.
                "cost_usd": _estimate_cost_usd(model, tokens_in, tokens_out),
            }
        return response.choices[0].message.content or ""

    def get_last_usage(self) -> dict | None:
        """Token usage from the most recent successful chat()/chat_with_image()
        call, or None if none has been made yet. See core/cost_tracker.py for
        how callers fold this into AnalystState.token_usage."""
        return self._last_usage


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient()
