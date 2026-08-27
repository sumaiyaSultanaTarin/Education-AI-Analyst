import hashlib
import uuid
from pathlib import Path

import chromadb
import pytest

from tools.web_search_tools import WebSearchError

SAMPLE_DOCS_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


@pytest.fixture
def sample_docs_dir() -> Path:
    return SAMPLE_DOCS_DIR


@pytest.fixture
def fake_embed_fn():
    """Deterministic stand-in for tools/embedding_tools.embed_texts.

    Avoids downloading the real sentence-transformers model in tests — hashes
    each text into a small fixed-size vector instead of a real embedding.
    """

    def _embed(texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()[:8]
            vectors.append([byte / 255 for byte in digest])
        return vectors

    return _embed


@pytest.fixture
def chroma_collection():
    """An ephemeral, in-memory Chroma collection — no disk persistence.

    EphemeralClient() shares its underlying in-process system cache across
    calls with identical settings, so a fixed collection name would leak
    data between tests within the same run. A random name per test keeps
    each test's collection isolated regardless of that caching.
    """
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection(f"test-collection-{uuid.uuid4().hex}")


@pytest.fixture(autouse=True)
def _no_real_web_search(monkeypatch):
    """Stops DataAnalystAgent.analyze_all() from making a real Tavily call
    as a side effect of running the suite, now that a real TAVILY_API_KEY
    can legitimately live in .env (see tools/web_search_tools.py) — same
    "no real network/model calls in tests" rationale as fake_embed_fn and
    chroma_collection above. Only patches the name as imported into
    agents.data_analyst_agent, so tests/test_web_search_tools.py (which
    calls tools.web_search_tools.search_web directly) is unaffected.
    """

    def _fake_search_web(*args, **kwargs):
        raise WebSearchError("no TAVILY_API_KEY in tests — see conftest._no_real_web_search")

    monkeypatch.setattr("agents.data_analyst_agent.search_web", _fake_search_web)
