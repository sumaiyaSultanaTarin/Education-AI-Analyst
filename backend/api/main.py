from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import documents, hitl, memory, observability, report, sessions
from core.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Not at import time (see api/session_store.py's load_sessions_from_disk
    # docstring) — only a real app startup should reload data/sessions.db,
    # not merely importing this module from a test.
    from api.session_store import load_sessions_from_disk, sessions

    restored = load_sessions_from_disk()
    sessions.update(restored)
    if restored:
        logger.info("Restored %d session(s) from data/sessions.db", len(restored))
    yield


app = FastAPI(title="Education AI Analyst", version="0.1.0", lifespan=_lifespan)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(report.router)
app.include_router(hitl.router)
app.include_router(memory.router)
app.include_router(observability.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
