"""
API-specific Pydantic schemas.

These complement backend/models/schemas.py with shapes that are specific to
HTTP request/response bodies for endpoints that don't map 1:1 onto the core
domain models (e.g. a health check response, or a ticket list response that
wraps multiple tickets with pagination-ish metadata).
"""

from datetime import datetime

from pydantic import BaseModel

from backend.models.schemas import SupportTicket


class HealthResponse(BaseModel):
    status: str
    app_env: str
    llm_model: str


class TicketListResponse(BaseModel):
    session_id: str
    count: int
    tickets: list[SupportTicket]


class AnalyticsLogEntry(BaseModel):
    """One row of analytics data, as returned to the dashboard frontend."""
    id: int
    session_id: str
    user_id: str
    user_query: str
    intent: str | None
    intent_confidence: float
    tool_used: str
    response: str
    response_confidence: float
    escalated: bool
    processing_time_ms: float
    created_at: datetime


class AnalyticsSummaryResponse(BaseModel):
    total_interactions: int
    escalation_rate: float
    average_confidence: float
    average_processing_time_ms: float
    intent_breakdown: dict[str, int]
    tool_usage_breakdown: dict[str, int]
    recent_logs: list[AnalyticsLogEntry]


class ClearHistoryRequest(BaseModel):
    session_id: str
