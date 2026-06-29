"""
Repository layer for support tickets.

Used by the create_support_ticket and check_ticket_status tools (see
backend/tools/) so those tool functions stay thin — they just call these
repository functions rather than embedding raw SQL/ORM logic in tool code.
"""

from sqlalchemy.orm import Session

from backend.database.models import Ticket


def create_ticket(
    db: Session,
    session_id: str,
    user_id: str,
    subject: str,
    description: str,
    category: str,
    priority: str = "medium",
) -> Ticket:
    ticket = Ticket(
        session_id=session_id,
        user_id=user_id,
        subject=subject,
        description=description,
        category=category,
        priority=priority,
        status="open",
    )
    db.add(ticket)
    db.flush()  # populates ticket.id immediately so callers can use it
    return ticket


def get_ticket_by_id(db: Session, ticket_id: int) -> Ticket | None:
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()


def get_tickets_for_session(db: Session, session_id: str) -> list[Ticket]:
    return (
        db.query(Ticket)
        .filter(Ticket.session_id == session_id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


def update_ticket_status(db: Session, ticket_id: int, status: str) -> Ticket | None:
    ticket = get_ticket_by_id(db, ticket_id)
    if ticket is not None:
        ticket.status = status
        db.flush()
    return ticket
