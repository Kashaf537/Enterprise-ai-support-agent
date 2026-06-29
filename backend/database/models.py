"""
SQLAlchemy ORM table definitions.

Four tables:
  - conversations: one row per chat session (groups messages together)
  - messages: one row per user/assistant turn — this IS the conversation
    memory the spec asks for ("system should remember previous messages")
  - tickets: one row per support ticket created by the create_support_ticket
    tool
  - interaction_logs: one row per agent invocation, capturing everything the
    spec's "Logging" requirement asks for (query, retrieved context, tool
    used, response, timestamp) — this also feeds the analytics dashboard
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.db import Base


def _utc_now() -> datetime:
    """
    Returns the current UTC time as a naive datetime (no tzinfo attached).

    Why naive rather than timezone-aware? SQLite has no native timezone-aware
    datetime type — values are stored as plain text either way — and the
    rest of this app (Pydantic schemas' `default_factory=datetime.utcnow`,
    JSON timestamps returned to the frontend) is consistently naive-UTC too.
    Mixing aware and naive datetimes is what actually causes bugs; using
    `datetime.now(timezone.utc).replace(tzinfo=None)` keeps the VALUE
    correct (true UTC) while keeping the type consistent across the app,
    without the deprecated `datetime.utcnow()` call.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(Base):
    """One row per chat session. session_id is the stable key the frontend
    generates once per browser tab / chat window and reuses for every
    message in that conversation.
    """
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    """
    One row per single chat turn. `role` is either 'user' or 'assistant',
    matching the format LangChain/LLM chat history expects, so memory.py
    can load these rows straight into a prompt without reshaping them.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Ticket(Base):
    """A support ticket, created by the create_support_ticket tool when the
    agent decides a human-trackable issue needs to be logged.
    """
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="anonymous")
    subject: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class InteractionLog(Base):
    """
    One row per agent invocation (i.e. one full pass through the LangGraph
    workflow for a single user message). This is what powers the Analytics
    Dashboard: intent, confidence, tool used, retrieved docs, response time.
    """
    __tablename__ = "interaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="anonymous")

    user_query: Mapped[str] = mapped_column(Text)
    retrieved_context: Mapped[str] = mapped_column(Text, nullable=True)  # JSON-encoded list of sources
    intent: Mapped[str] = mapped_column(String(64), nullable=True)
    intent_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    tool_used: Mapped[str] = mapped_column(String(64), default="none")
    response: Mapped[str] = mapped_column(Text)
    response_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    escalated: Mapped[bool] = mapped_column(default=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
