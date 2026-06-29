"""
Analytics endpoints.

Powers the spec's "Analytics Dashboard" requirement: intent breakdown,
confidence trends, tool usage, escalation rate, and recent interaction logs.
The Streamlit frontend calls this to render charts/tables rather than
querying the database directly — keeping the frontend decoupled from the
database schema.
"""

from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.api_schemas import AnalyticsLogEntry, AnalyticsSummaryResponse
from backend.database.db import get_db
from backend.database.log_repository import get_logs_for_session, get_recent_logs

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _log_to_entry(log) -> AnalyticsLogEntry:
    return AnalyticsLogEntry(
        id=log.id,
        session_id=log.session_id,
        user_id=log.user_id,
        user_query=log.user_query,
        intent=log.intent,
        intent_confidence=log.intent_confidence,
        tool_used=log.tool_used,
        response=log.response,
        response_confidence=log.response_confidence,
        escalated=log.escalated,
        processing_time_ms=log.processing_time_ms,
        created_at=log.created_at,
    )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """
    Aggregates the most recent `limit` interaction logs into summary
    statistics: escalation rate, average confidence, average processing
    time, and breakdowns by intent and by tool used.
    """
    logs = get_recent_logs(db, limit=limit)

    if not logs:
        return AnalyticsSummaryResponse(
            total_interactions=0,
            escalation_rate=0.0,
            average_confidence=0.0,
            average_processing_time_ms=0.0,
            intent_breakdown={},
            tool_usage_breakdown={},
            recent_logs=[],
        )

    total = len(logs)
    escalated_count = sum(1 for l in logs if l.escalated)
    avg_confidence = sum(l.response_confidence for l in logs) / total
    avg_time = sum(l.processing_time_ms for l in logs) / total

    intent_breakdown = dict(Counter(l.intent or "Unknown" for l in logs))
    tool_breakdown = dict(Counter(l.tool_used or "none" for l in logs))

    return AnalyticsSummaryResponse(
        total_interactions=total,
        escalation_rate=round(escalated_count / total, 4),
        average_confidence=round(avg_confidence, 4),
        average_processing_time_ms=round(avg_time, 2),
        intent_breakdown=intent_breakdown,
        tool_usage_breakdown=tool_breakdown,
        recent_logs=[_log_to_entry(l) for l in logs],
    )


@router.get("/session/{session_id}", response_model=list[AnalyticsLogEntry])
def get_session_analytics(session_id: str, db: Session = Depends(get_db)) -> list[AnalyticsLogEntry]:
    """Returns the full interaction log history for one specific session —
    useful for debugging or reviewing a single conversation's analytics.
    """
    logs = get_logs_for_session(db, session_id)
    return [_log_to_entry(l) for l in logs]
