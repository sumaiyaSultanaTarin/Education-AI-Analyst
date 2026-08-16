from fastapi import FastAPI

from api.routes import documents, graph_viewer, hitl, memory, messages, report, sessions
from core.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Education AI Analyst", version="0.1.0")
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(report.router)
app.include_router(hitl.router)
app.include_router(memory.router)
app.include_router(messages.router)
app.include_router(graph_viewer.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
