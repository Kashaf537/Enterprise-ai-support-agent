"""
Tool: escalate_to_human

Marks the current interaction as escalated and creates a high-priority
ticket flagged for human review. This is called either:
  1. Automatically by the agent graph when response_confidence falls below
     the escalation threshold (see backend/graph — escalation_check node)
  2. Explicitly when the customer asks to speak to a human, or the issue
     matches an automatic-escalation rule from company_policies.md
     (e.g. suspected account security issue, denied refund dispute)
"""

from pydantic import BaseModel

from backend.database.db import get_db_session
from backend.database.ticket_repository import create_ticket
from backend.utils.logger import logger


class EscalateToHumanInput(BaseModel):
    session_id: str
    user_id: str
    reason: str
    conversation_summary: str
    category: str = "General Inquiry"


def escalate_to_human(
    session_id: str,
    user_id: str,
    reason: str,
    conversation_summary: str,
    category: str = "General Inquiry",
) -> dict:
    """
    Creates a high-priority ticket marked for human follow-up and returns a
    confirmation the agent can relay to the customer, reassuring them a
    human will take over.
    """
    logger.warning(
        "Tool called: escalate_to_human(session_id='{}', reason='{}')", session_id, reason
    )

    with get_db_session() as db:
        ticket = create_ticket(
            db,
            session_id=session_id,
            user_id=user_id,
            subject=f"[ESCALATED] {reason}",
            description=conversation_summary,
            category=category,
            priority="high",
        )
        ticket_id = ticket.id

    return {
        "escalated": True,
        "ticket_id": ticket_id,
        "message": (
            "I've escalated this to our human support team — "
            f"ticket #{ticket_id} has been created with high priority. "
            "Someone will follow up with you shortly."
        ),
    }
