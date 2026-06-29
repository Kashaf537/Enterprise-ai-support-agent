"""
Ticket endpoints.

Exposes ticket data created by the create_support_ticket / escalate_to_human
tools as proper REST resources, separate from the chat flow — useful for a
"My Tickets" panel in the frontend, or for a support agent's own dashboard
to look up what the AI has filed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.ticket_repository import get_ticket_by_id, get_tickets_for_session
from backend.models.schemas import SupportTicket

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _to_schema(ticket) -> SupportTicket:
    return SupportTicket(
        ticket_id=ticket.id,
        session_id=ticket.session_id,
        user_id=ticket.user_id,
        subject=ticket.subject,
        description=ticket.description,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at,
    )


@router.get("/session/{session_id}", response_model=list[SupportTicket])
def list_tickets_for_session(session_id: str, db: Session = Depends(get_db)) -> list[SupportTicket]:
    tickets = get_tickets_for_session(db, session_id)
    return [_to_schema(t) for t in tickets]


@router.get("/{ticket_id}", response_model=SupportTicket)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> SupportTicket:
    ticket = get_ticket_by_id(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket #{ticket_id} not found")
    return _to_schema(ticket)
