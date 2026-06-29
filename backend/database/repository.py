"""
Repository layer for conversations & messages.

Why a repository layer at all?
Without this, every module that needs to "save a message" would write its
own raw SQLAlchemy query, duplicating logic and making it easy for one
module to do it slightly differently (and buggily) than another. This file
is the ONE place that knows how to read/write conversation data — everything
else (memory.py, api routes) calls these functions and never touches
SQLAlchemy session objects directly for this domain.
"""

from sqlalchemy.orm import Session

from backend.database.models import Conversation, Message


def get_or_create_conversation(db: Session, session_id: str, user_id: str = "anonymous") -> Conversation:
    """
    Fetches the Conversation row for this session_id, creating one if it
    doesn't exist yet. This is what lets the frontend just send a
    session_id on every request without separately calling a "start
    conversation" endpoint first.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if conversation is None:
        conversation = Conversation(session_id=session_id, user_id=user_id)
        db.add(conversation)
        db.flush()  # assigns conversation.id without fully committing yet
    return conversation


def add_message(db: Session, session_id: str, role: str, content: str, user_id: str = "anonymous") -> Message:
    """Appends one message (user or assistant) to a conversation's history."""
    conversation = get_or_create_conversation(db, session_id, user_id)
    message = Message(conversation_id=conversation.id, role=role, content=content)
    db.add(message)
    db.flush()
    return message


def get_recent_messages(db: Session, session_id: str, limit: int = 10) -> list[Message]:
    """
    Returns the most recent `limit` messages for a session, in
    chronological order (oldest first) — the order an LLM expects when
    reading back chat history.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if conversation is None:
        return []

    # Fetch newest-first (so LIMIT keeps the most recent ones), then reverse
    # back to chronological order for the caller.
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def clear_conversation(db: Session, session_id: str) -> None:
    """Deletes a conversation and all its messages (cascade) — used by a
    'New Chat' / 'Clear History' button in the frontend.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if conversation is not None:
        db.delete(conversation)
