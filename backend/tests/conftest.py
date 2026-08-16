import hashlib
import uuid
from pathlib import Path

import chromadb
import pytest

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
