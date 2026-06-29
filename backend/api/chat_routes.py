"""
Chat endpoints.

The core of the public API surface: send a message, get back a full
ChatResponse (response text + intent + confidence + tool used + retrieved
docs + timing). Also exposes a clear-history endpoint for a "New Chat"
button in the frontend.
"""

from fastapi import APIRouter, HTTPException

from backend.memory.conversation_memory import memory
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.agent_service import handle_user_message
from backend.utils.logger import logger

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(request: ChatRequest) -> ChatResponse:
    """
    Processes one user message through the full agent workflow (intent
    detection, tool calling, RAG retrieval, response generation, confidence
    check, escalation) and returns the result.
    """
    try:
        response = handle_user_message(
            session_id=request.session_id,
            user_id=request.user_id,
            message=request.message,
        )
        return response
    except Exception as e:
        # Anything that escapes the graph's own internal fallbacks (e.g. a
        # genuine network failure calling Groq) becomes a clean 500 rather
        # than an unhandled stack trace leaking to the client.
        logger.exception("Unhandled error processing chat message for session {}", request.session_id)
        raise HTTPException(status_code=500, detail=f"Failed to process message: {e}") from e


@router.delete("/{session_id}")
def clear_chat_history(session_id: str) -> dict:
    """Clears all stored history for a session — used by a 'New Chat' button."""
    memory.clear(session_id)
    return {"session_id": session_id, "cleared": True}


@router.get("/{session_id}/history")
def get_chat_history(session_id: str) -> dict:
    """Returns the stored message history for a session, e.g. to restore a
    chat window after a page refresh.
    """
    history = memory.load_history(session_id)
    return {"session_id": session_id, "messages": history}
