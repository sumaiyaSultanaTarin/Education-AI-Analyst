from types import SimpleNamespace

from core.config import Settings
from core.llm_client import LLMClient


class _FakeCompletions:
    def __init__(self, content: str, usage: SimpleNamespace | None):
        self._content = content
        self._usage = usage

    def create(self, model, messages, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))],
            usage=self._usage,
        )


class _FakeOpenAI:
    def __init__(self, content: str, usage: SimpleNamespace | None):
        self.chat = SimpleNamespace(completions=_FakeCompletions(content, usage))


def _client_with_fake_openai(content: str, usage: SimpleNamespace | None) -> LLMClient:
    client = LLMClient(
        settings=Settings(openrouter_api_key="test-key", openrouter_fallback_models=["fake/model"])
    )
    client._client = _FakeOpenAI(content, usage)
    return client


def test_chat_records_usage_after_a_successful_call():
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=5)
    client = _client_with_fake_openai("hello", usage)

    reply = client.chat([{"role": "user", "content": "hi"}])

    assert reply == "hello"
    assert client.last_usage == {
        "model": "fake/model",
        "tokens_in": 12,
        "tokens_out": 5,
        "cost_usd": 0.0,
    }


def test_last_usage_stays_none_when_provider_omits_usage():
    client = _client_with_fake_openai("hello", usage=None)

    client.chat([{"role": "user", "content": "hi"}])

    assert client.last_usage is None
