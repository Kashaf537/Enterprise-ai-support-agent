Architecture

Overview

The Enterprise AI Support Agent is built as three layers: a Streamlit
frontend, a FastAPI backend, and a LangGraph agent workflow that the
backend invokes for every chat message. See architecture_diagram.svg in
this folder for the visual.

Request lifecycle

1. The user types a message in the Streamlit chat window (frontend/app.py).
2. The frontend sends a POST request to /api/v1/chat on the FastAPI backend,
   including a stable session_id generated once per browser session.
3. The chat route (backend/api/chat_routes.py) calls
   handle_user_message() in backend/services/agent_service.py.
4. agent_service loads the conversation's recent history from the database
   (backend/memory/conversation_memory.py), builds an AgentState object,
   and invokes the compiled LangGraph workflow.
5. The graph runs through its nodes in order:
     intent_detection -> tool_decision -> (tool_execution if needed)
     -> needs_knowledge_check -> (retrieve_documents if needed)
     -> generate_response -> confidence_check -> save_memory
6. confidence_check applies the two business rules from the spec:
   below 30% confidence, the conversation is automatically escalated to a
   human (a high-priority ticket is created); below 60%, the agent asks a
   clarifying question instead of guessing.
7. save_memory persists the turn so the next message in this session has
   the right context.
8. agent_service logs the full interaction (intent, confidence, tool used,
   retrieved documents, timing) to the interaction_logs table for the
   analytics dashboard, then returns a ChatResponse.
9. The frontend renders the response along with its metadata panel
   (intent, confidence, tool used, response time, retrieved documents).

Why LangGraph and not a single long prompt or a simple if/else chain

A single mega-prompt asking the LLM to "classify intent AND decide on a
tool AND write a response AND rate your own confidence" in one call is
brittle: any one part going wrong (e.g. malformed JSON for the tool
decision) corrupts the entire response. Splitting these into separate
graph nodes means each step can be tested, mocked, and reasoned about in
isolation, and a failure in one step (handled via fallback values in each
agent module) doesn't take down the whole pipeline.

A plain if/else chain could express the same flow, but LangGraph gives us:
  - A formal state object (AgentState) that every node reads/writes, so
    data dependencies between steps are explicit and validated.
  - Conditional edges as first-class objects (route_after_tool_decision,
    route_after_knowledge_check) that are easy to unit test in isolation
    from the nodes themselves.
  - A natural place to add features later (parallel node execution, retry
    policies, checkpointing) without restructuring the whole pipeline.

Why retrieval is sometimes skipped

If a tool already produced a complete, self-contained answer (e.g.
reset_password generated a real reset link, or calculate_refund computed
an exact dollar amount), running RAG retrieval afterward adds latency for
no benefit — there's no document to look up to explain "your refund is
$132.67". The needs_knowledge_check node (backend/graph/nodes_retrieval.py)
encodes this as a simple rule-based check against a fixed set of
self-sufficient tools, rather than asking the LLM to decide — it's a
deterministic optimization, not a judgment call.

Why confidence is blended, not purely LLM-reported

The response generation agent (backend/agents/response_generator.py) asks
the LLM to self-report a confidence score, but LLMs can be overconfident in
free-text self-assessment. combine_confidence() blends this self-reported
score (70% weight) with the measured RAG similarity score (30% weight),
anchoring part of the final number to something objectively measurable.
This makes the escalation trigger more trustworthy than either signal
alone.

Why tool decision and tool execution are separate nodes

tool_decision_node only calls the LLM to decide IF and WHICH tool is
needed — it has no side effects. tool_execution_node is the only node that
actually performs an action (writing to the database, simulating an email
send). Keeping these separate means the "should we act" reasoning can be
tested without triggering real side effects, and the "perform the action"
code path is simple enough to not need an LLM call at all.

Data flow for conversation memory vs analytics logs

These are two different tables for two different purposes:
  - messages (backend/database/models.py: Message) stores the raw
    user/assistant text used to give the LLM conversation context on the
    next turn. This is "memory".
  - interaction_logs stores everything ELSE about a turn — intent,
    confidence scores, which tool ran, which documents were retrieved,
    processing time — used purely for the analytics dashboard, never fed
    back into the LLM's context. Mixing these into one table would force
    every memory read to also load unrelated analytics fields.

Module boundaries

  backend/rag       - chunking, embedding, ChromaDB, the retrieve() function
  backend/database  - SQLAlchemy engine, models, and repository functions
  backend/memory     - translates DB rows into LLM-ready chat history
  backend/tools      - the 6 callable actions + the dispatch registry
  backend/agents     - the 3 LLM-calling reasoning steps (intent, tool
                        decision, response generation)
  backend/graph      - LangGraph nodes and the compiled workflow
  backend/services   - llm_client.py (shared Groq client) and
                        agent_service.py (top-level orchestrator)
  backend/api        - FastAPI routers and the app entrypoint
  backend/models     - shared Pydantic schemas used across all the above
  frontend           - Streamlit chat UI and analytics dashboard

Each layer only imports from the layers below it in this list (e.g.
backend/graph imports backend/agents and backend/tools, but backend/tools
never imports backend/graph) — this keeps the dependency direction
one-way and makes the system easier to reason about as it grows.
