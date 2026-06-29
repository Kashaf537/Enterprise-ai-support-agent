"""
Tool: check_ticket_status

Looks up an existing ticket by id, or lists all tickets for the current
session if no id is given. Used when a customer asks "what's the status of
my ticket?" or "what tickets do I have open?".
"""

from pydantic import BaseModel

from backend.database.db import get_db_session
from backend.database.ticket_repository import get_ticket_by_id, get_tickets_for_session
from backend.utils.logger import logger


class CheckTicketStatusInput(BaseModel):
    session_id: str
    ticket_id: int | None = None


def check_ticket_status(session_id: str, ticket_id: int | None = None) -> dict:
    """
    If ticket_id is given, returns that single ticket's details.
    Otherwise, returns a summary of all tickets tied to this session.
    """
    logger.info("Tool called: check_ticket_status(session_id='{}', ticket_id={})", session_id, ticket_id)

    with get_db_session() as db:
        if ticket_id is not None:
            ticket = get_ticket_by_id(db, ticket_id)
            if ticket is None:
                return {"found": False, "message": f"No ticket found with id #{ticket_id}."}

            return {
                "found": True,
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status,
                "priority": ticket.priority,
                "category": ticket.category,
                "created_at": ticket.created_at.isoformat(),
            }

        tickets = get_tickets_for_session(db, session_id)
        if not tickets:
            return {"found": False, "message": "You have no support tickets on file."}

        return {
            "found": True,
            "count": len(tickets),
            "tickets": [
                {"ticket_id": t.id, "subject": t.subject, "status": t.status, "priority": t.priority}
                for t in tickets
            ],
        }
