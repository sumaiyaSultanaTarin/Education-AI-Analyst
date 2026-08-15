from fastapi import FastAPI

from api.routes import documents, sessions
from core.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Education AI Analyst", version="0.1.0")
app.include_router(sessions.router)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
