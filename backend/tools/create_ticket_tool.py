"""
Tool: create_support_ticket

Creates a persistent support ticket in the database. The agent calls this
when a customer's issue needs human follow-up or can't be resolved purely
through documentation/automation (e.g. a bug report, a billing dispute that
needs investigation, an account security concern).
"""

from pydantic import BaseModel, Field

from backend.database.db import get_db_session
from backend.database.ticket_repository import create_ticket
from backend.models.schemas import IntentCategory, TicketPriority
from backend.utils.logger import logger


class CreateSupportTicketInput(BaseModel):
    session_id: str
    user_id: str
    subject: str = Field(..., description="Short summary of the issue, e.g. 'API returning 401 errors'")
    description: str = Field(..., description="Full description of the customer's issue")
    category: IntentCategory
    priority: TicketPriority = TicketPriority.MEDIUM


def create_support_ticket(
    session_id: str,
    user_id: str,
    subject: str,
    description: str,
    category: str,
    priority: str = "medium",
) -> dict:
    """
    Creates a support ticket and returns a confirmation dict including the
    new ticket_id, which the agent should mention to the customer (e.g.
    "I've created ticket #14 for you").
    """
    logger.info(
        "Tool called: create_support_ticket(subject='{}', category='{}', priority='{}')",
        subject, category, priority,
    )

    with get_db_session() as db:
        ticket = create_ticket(
            db,
            session_id=session_id,
            user_id=user_id,
            subject=subject,
            description=description,
            category=category,
            priority=priority,
        )
        ticket_id = ticket.id  # capture before session closes

    return {
        "ticket_id": ticket_id,
        "status": "open",
        "message": f"Support ticket #{ticket_id} created successfully.",
    }
