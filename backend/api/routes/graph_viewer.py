"""`/sessions/{id}/graph` — current graph definition (mermaid + JSON) for the
Graph Viewer frontend panel (docs/architecture.md §6).

The pipeline topology is fixed (not built differently per session), so this
returns static data — `session_id` only exists in the path for API-shape
consistency with the other /sessions/{id}/* routes and in case per-session
routing (e.g. skipping agents with nothing to do) becomes worth surfacing
later. Kept as its own module rather than `graph.py` to avoid any confusion
with the top-level `graph/` package (graph.state, graph.graph_builder, ...)
imported throughout the backend.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.session_store import sessions

router = APIRouter(prefix="/sessions", tags=["graph"])

# Reality has two separate compiled LangGraph graphs, run by two different
# endpoints (see graph/graph_builder.py and graph/report_graph_builder.py) —
# shown here as one flow since that's how a user experiences the pipeline.
_MERMAID = """graph TD
    subgraph Intake["Intake Graph — POST /sessions/{id}/run"]
        Start([Uploaded documents]) --> Supervisor1[Supervisor]
        Supervisor1 -->|pdf/docx/pptx/xlsx| DocIngest[Document Ingestion Agent]
        Supervisor1 -->|image| OCR[Vision/OCR Agent]
        Supervisor1 -->|social_csv| Social[Social Intelligence Agent]
        DocIngest --> Supervisor1
        OCR --> Supervisor1
        Social --> Supervisor1
        Supervisor1 -->|all documents processed| IntakeEnd([intake complete])
    end

    subgraph Report["Report Graph — POST /sessions/{id}/generate-report"]
        IntakeEnd --> DataAnalyst[Data Analyst Agent]
        DataAnalyst --> RAG[Knowledge/RAG Agent]
        RAG --> ReportGen[Report Generator Agent]
        ReportGen --> QA[QA/Critic Agent]
        QA -->|issues found| ReportGen
        QA -->|passes checks| HITL{{Human Approval - interrupt}}
        HITL -->|approved| Done([Final report delivered])
        HITL -->|rejected/retry| ReportGen
    end
"""

_NODES = [
    {"id": "document_ingestion", "label": "Document Ingestion Agent", "graph": "intake"},
    {"id": "vision_ocr", "label": "Vision/OCR Agent", "graph": "intake"},
    {"id": "social_intelligence", "label": "Social Intelligence Agent", "graph": "intake"},
    {"id": "data_analyst", "label": "Data Analyst Agent", "graph": "report"},
    {"id": "knowledge_rag", "label": "Knowledge/RAG Agent", "graph": "report"},
    {"id": "report_generator", "label": "Report Generator Agent", "graph": "report"},
    {"id": "qa_critic", "label": "QA/Critic Agent", "graph": "report"},
    {"id": "hitl_approval", "label": "Human Approval (interrupt)", "graph": "report"},
]

_EDGES = [
    {"from": "document_ingestion", "to": "supervisor"},
    {"from": "vision_ocr", "to": "supervisor"},
    {"from": "social_intelligence", "to": "supervisor"},
    {"from": "data_analyst", "to": "knowledge_rag"},
    {"from": "knowledge_rag", "to": "report_generator"},
    {"from": "report_generator", "to": "qa_critic"},
    {"from": "qa_critic", "to": "report_generator", "label": "issues found"},
    {"from": "qa_critic", "to": "hitl_approval", "label": "passes checks"},
    {"from": "hitl_approval", "to": "report_generator", "label": "rejected/retry"},
]


class GraphDefinitionResponse(BaseModel):
    mermaid: str
    nodes: list[dict]
    edges: list[dict]


@router.get("/{session_id}/graph", response_model=GraphDefinitionResponse)
def get_graph_definition(session_id: str) -> GraphDefinitionResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return GraphDefinitionResponse(mermaid=_MERMAID, nodes=_NODES, edges=_EDGES)
