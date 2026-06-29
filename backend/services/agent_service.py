"""
Top-level Agent Service.

This is the single function the API layer (and Streamlit, if calling the
backend in-process) should call to handle one user message end-to-end. It:

  1. Loads conversation history from memory
  2. Builds the initial AgentState
  3. Runs the compiled LangGraph workflow
  4. Times the whole operation
  5. Writes an InteractionLog row for analytics
  6. Returns a clean ChatResponse

Keeping this orchestration in one place (rather than spreading "load
history, run graph, log it" across every API route) means the FastAPI
route handler stays a thin wrapper, and the same function could be reused
by a CLI tool, a batch script, or tests without any FastAPI dependency.
"""

import time

from backend.database.db import get_db_session
from backend.database.log_repository import log_interaction
from backend.graph.workflow import get_support_agent_graph
from backend.memory.conversation_memory import memory
from backend.models.schemas import AgentState, ChatResponse
from backend.utils.logger import logger


def handle_user_message(session_id: str, user_id: str, message: str) -> ChatResponse:
    """
    Runs one full agent turn for `message` and returns the response,
    including all metadata the analytics dashboard needs.
    """
    start_time = time.perf_counter()

    chat_history = memory.load_history(session_id)

    initial_state = AgentState(
        session_id=session_id,
        user_id=user_id,
        user_message=message,
        chat_history=chat_history,
    )

    graph = get_support_agent_graph()

    # LangGraph's .invoke() runs the full workflow synchronously and
    # returns the final state (as a dict, since LangGraph serializes
    # Pydantic state through its internal channel mechanism — we
    # reconstruct it into our AgentState type for clean attribute access).
    raw_result = graph.invoke(initial_state)
    final_state = AgentState(**raw_result)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    final_state.processing_time_ms = elapsed_ms

    logger.info(
        "Handled message for session={} intent={} tool={} confidence={:.2f} escalated={} time={:.0f}ms",
        session_id, final_state.intent.value if final_state.intent else None,
        final_state.tool_name.value, final_state.response_confidence,
        final_state.escalated, elapsed_ms,
    )

    # Persist analytics log — separate from conversation memory (which
    # just stores the raw chat turn); this captures the full metadata the
    # dashboard needs (intent, confidence, tool, retrieved docs, timing).
    with get_db_session() as db:
        log_interaction(
            db,
            session_id=session_id,
            user_id=user_id,
            user_query=message,
            response=final_state.final_response,
            intent=final_state.intent.value if final_state.intent else "Unknown",
            intent_confidence=final_state.intent_confidence,
            response_confidence=final_state.response_confidence,
            tool_used=final_state.tool_name.value,
            retrieved_documents=final_state.retrieved_documents,
            escalated=final_state.escalated,
            processing_time_ms=elapsed_ms,
        )

    return ChatResponse(
        session_id=session_id,
        response=final_state.final_response,
        intent=final_state.intent,
        confidence=final_state.response_confidence,
        tool_used=final_state.tool_name,
        retrieved_documents=final_state.retrieved_documents,
        escalated=final_state.escalated,
        processing_time_ms=elapsed_ms,
    )
