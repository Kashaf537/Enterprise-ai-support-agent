"""
Conversation memory manager.

Why does this need its own module instead of just calling repository.py
directly from the agent graph?

The database repository deals in SQLAlchemy ORM objects (Message rows with
.role, .content, .created_at, etc). The LLM / LangChain side wants chat
history as plain dicts like {"role": "user", "content": "..."} or as
LangChain message objects. This module is the *translation layer* — it's
the only place that knows both "how the DB stores history" and "how the LLM
wants to consume it", so neither side needs to know about the other's shape.

This is also where we'd add memory strategies later (e.g. summarizing old
messages instead of just truncating) without touching the DB layer or the
agent graph.
"""

from backend.database.db import get_db_session
from backend.database.repository import add_message, clear_conversation, get_recent_messages
from backend.utils.logger import logger

# How many past turns (user+assistant pairs counted as individual messages)
# to include as context. Keeping this bounded avoids unbounded prompt growth
# in long conversations, which would otherwise slow down and eventually
# break the LLM call (context window limits, rising cost/latency).
MAX_HISTORY_MESSAGES = 12


class ConversationMemory:
    """
    Public interface the agent graph uses for reading and writing
    conversation history. One instance is effectively stateless — all real
    state lives in the database — so it's cheap to create per-request.
    """

    def load_history(self, session_id: str) -> list[dict]:
        """
        Returns the recent chat history for a session as a list of plain
        dicts: [{"role": "user", "content": "..."}, {"role": "assistant", ...}]

        This exact shape is what LangChain's prompt templates and most LLM
        chat APIs (including Groq's OpenAI-compatible format) expect, so it
        can be passed straight into a prompt with no further conversion.
        """
        with get_db_session() as db:
            messages = get_recent_messages(db, session_id, limit=MAX_HISTORY_MESSAGES)
            history = [{"role": m.role, "content": m.content} for m in messages]

        logger.debug("Loaded {} history messages for session {}", len(history), session_id)
        return history

    def save_turn(self, session_id: str, user_id: str, user_message: str, assistant_response: str) -> None:
        """
        Persists one complete turn (the user's message and the assistant's
        reply) to the database. Called once per agent invocation, after the
        graph has finished generating a response — never partway through,
        so a failed/incomplete turn never gets half-saved.
        """
        with get_db_session() as db:
            add_message(db, session_id, role="user", content=user_message, user_id=user_id)
            add_message(db, session_id, role="assistant", content=assistant_response, user_id=user_id)

        logger.debug("Saved turn for session {}", session_id)

    def clear(self, session_id: str) -> None:
        """Wipes a session's history — used by a 'New Chat' button."""
        with get_db_session() as db:
            clear_conversation(db, session_id)
        logger.info("Cleared conversation history for session {}", session_id)

    def format_history_for_prompt(self, history: list[dict]) -> str:
        """
        Renders chat history as a simple transcript string, used when
        building a plain-text prompt (rather than a structured messages
        list) for the LLM — e.g. inside the response-generation node where
        we want history embedded directly in a single prompt string.
        """
        if not history:
            return "(no previous conversation)"

        lines = []
        for turn in history:
            speaker = "Customer" if turn["role"] == "user" else "Support Agent"
            lines.append(f"{speaker}: {turn['content']}")
        return "\n".join(lines)


# Module-level singleton — cheap to share since the class holds no per-call
# state, everything is read fresh from the DB on each call.
memory = ConversationMemory()
