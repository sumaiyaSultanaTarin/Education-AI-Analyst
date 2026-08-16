"""LangGraph wiring for the document intake loop.

The Supervisor node picks the next unprocessed document from
state["documents"] and routes to whichever worker agent handles its type;
each worker returns control to the Supervisor rather than chaining directly
to the next worker (see docs/architecture.md §2.4/§8, "Supervisor as a hub,
not a chain"). Once every document is processed (or there are none), the
Supervisor routes to END.
"""

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.document_ingestion_agent import DocumentIngestionAgent
from agents.social_intel_agent import SocialIntelligenceAgent
from agents.vision_ocr_agent import VisionOCRAgent
from graph.state import AnalystState, DocumentRef

_NODE_BY_TYPE = {
    "pdf": "document_ingestion",
    "docx": "document_ingestion",
    "pptx": "document_ingestion",
    "xlsx": "document_ingestion",
    "image": "vision_ocr",
    "social_csv": "social_intelligence",
}

_OUTPUT_KEYS = (
    DocumentIngestionAgent.name,
    VisionOCRAgent.name,
    SocialIntelligenceAgent.name,
)


def _is_processed(state: AnalystState, document_id: str) -> bool:
    outputs = state["agent_outputs"]
    if any(document_id in outputs.get(key, {}) for key in _OUTPUT_KEYS):
        return True
    return any(err["document_id"] == document_id for err in state["errors"])


def _find_next_document(state: AnalystState) -> DocumentRef | None:
    for document in state["documents"]:
        if not _is_processed(state, document["document_id"]):
            return document
    return None


def _current_document(state: AnalystState) -> DocumentRef:
    return next(
        d for d in state["documents"] if d["document_id"] == state["current_document_id"]
    )


def _supervisor_node(state: AnalystState) -> AnalystState:
    next_document = _find_next_document(state)
    state["current_document_id"] = next_document["document_id"] if next_document else None
    return state


def _route_from_supervisor(state: AnalystState) -> str:
    if state["current_document_id"] is None:
        return END
    return _NODE_BY_TYPE[_current_document(state)["type"]]


def build_graph(
    document_ingestion_agent: DocumentIngestionAgent | None = None,
    vision_ocr_agent: VisionOCRAgent | None = None,
    social_intel_agent: SocialIntelligenceAgent | None = None,
) -> CompiledStateGraph:
    """Compile the supervisor -> {document_ingestion, vision_ocr, social_intelligence}
    -> supervisor loop.

    Agents are injectable so tests (and callers wanting a non-default OCR
    LLM client) don't have to go through the real OpenRouter client.
    """
    ingestion_agent = document_ingestion_agent or DocumentIngestionAgent()
    ocr_agent = vision_ocr_agent or VisionOCRAgent()
    social_agent = social_intel_agent or SocialIntelligenceAgent()

    def _document_ingestion_node(state: AnalystState) -> AnalystState:
        return ingestion_agent.ingest(state, _current_document(state))

    def _vision_ocr_node(state: AnalystState) -> AnalystState:
        return ocr_agent.process_image(state, _current_document(state))

    def _social_intelligence_node(state: AnalystState) -> AnalystState:
        return social_agent.process_csv(state, _current_document(state))

    graph = StateGraph(AnalystState)
    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("document_ingestion", _document_ingestion_node)
    graph.add_node("vision_ocr", _vision_ocr_node)
    graph.add_node("social_intelligence", _social_intelligence_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "document_ingestion": "document_ingestion",
            "vision_ocr": "vision_ocr",
            "social_intelligence": "social_intelligence",
            END: END,
        },
    )
    graph.add_edge("document_ingestion", "supervisor")
    graph.add_edge("vision_ocr", "supervisor")
    graph.add_edge("social_intelligence", "supervisor")

    return graph.compile()
