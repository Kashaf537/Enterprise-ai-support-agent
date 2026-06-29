"""
Repository layer for interaction logs — the audit trail / analytics data
source. Every full pass through the agent graph writes exactly one row here
via `log_interaction()`. The Streamlit analytics dashboard reads from this
table via `get_recent_logs()` / `get_logs_for_session()`.
"""

import json

from sqlalchemy.orm import Session

from backend.database.models import InteractionLog
from backend.models.schemas import RetrievedDocument


def log_interaction(
    db: Session,
    session_id: str,
    user_id: str,
    user_query: str,
    response: str,
    intent: str,
    intent_confidence: float,
    response_confidence: float,
    tool_used: str,
    retrieved_documents: list[RetrievedDocument],
    escalated: bool,
    processing_time_ms: float,
) -> InteractionLog:
    """
    Persists one full agent interaction. Retrieved documents are stored as
    a JSON string (just source + score, not full content, to keep rows
    small) since SQLite has no native array/JSON column type that we need
    here — JSON-as-text is the simplest portable approach.
    """
    retrieved_summary = json.dumps(
        [{"source": d.source, "score": d.similarity_score} for d in retrieved_documents]
    )

    log_entry = InteractionLog(
        session_id=session_id,
        user_id=user_id,
        user_query=user_query,
        retrieved_context=retrieved_summary,
        intent=intent,
        intent_confidence=intent_confidence,
        tool_used=tool_used,
        response=response,
        response_confidence=response_confidence,
        escalated=escalated,
        processing_time_ms=processing_time_ms,
    )
    db.add(log_entry)
    db.flush()
    return log_entry


def get_recent_logs(db: Session, limit: int = 50) -> list[InteractionLog]:
    """Used by the analytics dashboard to show the most recent interactions
    across ALL sessions/users.
    """
    return (
        db.query(InteractionLog)
        .order_by(InteractionLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_logs_for_session(db: Session, session_id: str) -> list[InteractionLog]:
    return (
        db.query(InteractionLog)
        .filter(InteractionLog.session_id == session_id)
        .order_by(InteractionLog.created_at.asc())
        .all()
    )
