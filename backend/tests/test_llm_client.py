"""Tests for core/llm_client.py.

Replaces LLMClient._client (the openai.OpenAI instance) with a fake exposing
just the .chat.completions.create(...) shape used by _call_model — avoids
any real network call or needing a real OPENROUTER_API_KEY.

Only covers the immediate-success path plus get_last_usage() bookkeeping.
Deliberately doesn't exercise the retry-then-fallback-to-next-model path:
_call_model is wrapped in tenacity's @retry with a real exponential backoff
(core/llm_client.py), so a test that actually triggers a retry would sleep
for real seconds — not worth it just to re-verify pre-existing retry logic
this change didn't touch.
"""

from core.config import Settings
from core.llm_client import LLMClient


class _FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content, prompt_tokens=10, completion_tokens=4):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(prompt_tokens, completion_tokens)


class _FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.calls: list[str] = []

    def create(self, model, messages, **kwargs):
        self.calls.append(model)
        return self._response


class _FakeChatNamespace:
    def __init__(self, completions):
        self.completions = completions


class _FakeOpenAIClient:
    def __init__(self, response):
        self.completions = _FakeCompletions(response)
        self.chat = _FakeChatNamespace(self.completions)


def _make_client(response, fallback_models=("model-a:free",), vision_models=("vision-a:free",)):
    settings = Settings(
        openrouter_api_key="test-key",
        openrouter_fallback_models=list(fallback_models),
        openrouter_vision_fallback_models=list(vision_models),
    )
    client = LLMClient(settings=settings)
    client._client = _FakeOpenAIClient(response)
    return client


def test_chat_returns_content_from_the_model():
    client = _make_client(_FakeResponse("hello there"))

    reply = client.chat([{"role": "user", "content": "hi"}])

    assert reply == "hello there"
    assert client._client.completions.calls == ["model-a:free"]


def test_chat_records_usage_for_get_last_usage():
    client = _make_client(_FakeResponse("hi", prompt_tokens=42, completion_tokens=7))

    client.chat([{"role": "user", "content": "hi"}])

    assert client.get_last_usage() == {
        "model": "model-a:free", "tokens_in": 42, "tokens_out": 7, "cost_usd": 0.0,
    }


def test_get_last_usage_is_none_before_any_call():
    client = _make_client(_FakeResponse("unused"))

    assert client.get_last_usage() is None


def test_chat_with_image_uses_the_vision_fallback_list_and_records_usage():
    client = _make_client(
        _FakeResponse("transcribed text", prompt_tokens=100, completion_tokens=20),
        vision_models=("vision-a:free", "vision-b:free"),
    )

    reply = client.chat_with_image(b"fake-bytes", "image/png", "transcribe this")

    assert reply == "transcribed text"
    assert client._client.completions.calls == ["vision-a:free"]
    assert client.get_last_usage()["model"] == "vision-a:free"
    assert client.get_last_usage()["tokens_in"] == 100
