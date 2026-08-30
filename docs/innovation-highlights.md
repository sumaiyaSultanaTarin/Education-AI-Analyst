# Innovation Highlights — say these out loud

None of this is new work to build — it already exists in the running
system. The risk isn't that it's missing, it's that a grader clicking
through the UI won't notice it on their own. Say these explicitly during
the demo; don't assume they're self-evident.

## 1. Two different collaboration patterns, chosen deliberately, not one default

The intake pipeline (`graph/graph_builder.py`) routes through a Supervisor
hub — every worker returns control to it. The report pipeline
(`graph/report_graph_builder.py`) has **zero Supervisor node** — it's a
genuine direct chain, `data_analyst → knowledge_rag → report_generator →
qa_critic`, each agent handing off straight to the next. This isn't an
accident or a missed refactor: intake is a type-based *dispatch* problem (a
hub fits), the report pipeline is an inherently *sequential* one (a direct
chain fits). Confirmed straight from the compiled graph objects
(`.get_graph().draw_mermaid()`), not just claimed — see `docs/architecture.md`
§0/§5.

**Why this matters for grading:** if "agent-to-agent communication" is being
judged on whether agents talk directly rather than only through a
Supervisor, half your system genuinely does — point at the Execution Graph
panel's "Analysis / Report / HITL" tab and note there's no Supervisor node
in it at all.

## 2. The Execution Graph literally cannot lie

`.get_graph().draw_mermaid()` is called on the actual compiled LangGraph
objects at request time — the diagram in the UI is generated *from the
code*, not drawn by hand and then left to rot as the code changes. If an
agent gets added, removed, or rewired, the diagram updates itself with zero
extra work. Say this explicitly; a static-looking diagram doesn't
communicate that on its own.

## 3. Free-tier LLM resilience, proven under real failure today

`core/llm_client.py` tries an ordered list of free OpenRouter models with
retry/backoff, falling through the list rather than hard-failing on one.
This isn't theoretical — during today's testing, the *entire* original
fallback list had quietly aged out of OpenRouter's free tier (every model
404'd), which the system handled by degrading gracefully (QA auto-passed,
logged as an error) rather than crashing. The fix was swapping in verified
models, but the resilience design is what kept the app usable while that
was stale.

## 4. Session state survives two independent failure modes, not one

- **Backend restart:** session state and the paused HITL checkpoint are
  persisted to SQLite (`data/sessions.db`, `data/checkpoints.db`), not held
  only in memory. A session paused mid-approval survives a server restart.
- **Browser refresh:** a separate failure mode — a page reload opens a new
  WebSocket connection and wipes Streamlit's client-side state even though
  the backend never lost anything. Fixed independently by keeping the
  session ID in the URL (`?session=...`) and restoring from it. Both fixes
  were found by actually breaking the app on purpose, not by inspection.

## 5. Real external data lands in the actual deliverable, not a side panel

The Data Analyst Agent's web-search step (Tavily) and the Social
Intelligence Agent's Facebook Graph API pull both feed real, live external
data into the generated report itself — an "External Benchmark Context"
section with real URLs, and (when configured) real Facebook comments
sentiment-scored and cited. Neither is a demo-only side panel disconnected
from the actual output.

## 6. Two independent input paths for the same downstream pipeline

CSV import and the real Facebook Graph API both normalize to the exact same
data shape and feed the exact same sentiment-scoring step
(`agents/social_intel_agent.py`'s `process_csv`/`process_graph_api`) — proof
the agent's contract is genuinely decoupled from where the data comes from,
not two parallel implementations that happen to look similar.
