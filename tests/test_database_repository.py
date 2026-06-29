"""
Tests for backend/database/repository.py, ticket_repository.py, and
log_repository.py — using the isolated in-memory db_session fixture from
conftest.py so these tests never touch the real database file.
"""

from backend.database.log_repository import get_recent_logs, log_interaction
from backend.database.repository import (
    add_message,
    clear_conversation,
    get_or_create_conversation,
    get_recent_messages,
)
from backend.database.ticket_repository import (
    create_ticket,
    get_ticket_by_id,
    get_tickets_for_session,
    update_ticket_status,
)


# --- Conversations & Messages ---

def test_get_or_create_conversation_creates_once(db_session):
    conv1 = get_or_create_conversation(db_session, "sess-1", "user-1")
    conv2 = get_or_create_conversation(db_session, "sess-1", "user-1")
    assert conv1.id == conv2.id  # same row returned, not duplicated


def test_add_message_and_get_recent_messages_preserves_order(db_session):
    add_message(db_session, "sess-1", "user", "first message")
    add_message(db_session, "sess-1", "assistant", "first reply")
    add_message(db_session, "sess-1", "user", "second message")

    messages = get_recent_messages(db_session, "sess-1", limit=10)

    assert [m.content for m in messages] == ["first message", "first reply", "second message"]


def test_get_recent_messages_respects_limit(db_session):
    for i in range(5):
        add_message(db_session, "sess-1", "user", f"message {i}")

    messages = get_recent_messages(db_session, "sess-1", limit=2)

    # Should return the 2 MOST RECENT messages, still in chronological order.
    assert [m.content for m in messages] == ["message 3", "message 4"]


def test_get_recent_messages_empty_for_unknown_session(db_session):
    messages = get_recent_messages(db_session, "does-not-exist")
    assert messages == []


def test_clear_conversation_removes_messages(db_session):
    add_message(db_session, "sess-1", "user", "hello")
    clear_conversation(db_session, "sess-1")
    db_session.flush()

    messages = get_recent_messages(db_session, "sess-1")
    assert messages == []


# --- Tickets ---

def test_create_ticket_assigns_id_and_defaults(db_session):
    ticket = create_ticket(
        db_session, session_id="sess-1", user_id="user-1",
        subject="Cannot log in", description="Login fails with 500 error",
        category="Account",
    )
    assert ticket.id is not None
    assert ticket.status == "open"
    assert ticket.priority == "medium"


def test_get_tickets_for_session_returns_only_that_sessions_tickets(db_session):
    create_ticket(db_session, "sess-1", "user-1", "Issue A", "desc", "Account")
    create_ticket(db_session, "sess-2", "user-2", "Issue B", "desc", "Billing")

    tickets = get_tickets_for_session(db_session, "sess-1")

    assert len(tickets) == 1
    assert tickets[0].subject == "Issue A"


def test_update_ticket_status(db_session):
    ticket = create_ticket(db_session, "sess-1", "user-1", "Issue", "desc", "Account")
    updated = update_ticket_status(db_session, ticket.id, "resolved")
    assert updated.status == "resolved"


def test_update_ticket_status_returns_none_for_unknown_id(db_session):
    result = update_ticket_status(db_session, 99999, "resolved")
    assert result is None


# --- Interaction Logs ---

def test_log_interaction_and_get_recent_logs(db_session):
    log_interaction(
        db_session, session_id="sess-1", user_id="user-1",
        user_query="how do refunds work?", response="Refunds are prorated.",
        intent="Refund", intent_confidence=0.9, response_confidence=0.85,
        tool_used="none", retrieved_documents=[], escalated=False,
        processing_time_ms=120.5,
    )

    logs = get_recent_logs(db_session, limit=10)

    assert len(logs) == 1
    assert logs[0].intent == "Refund"
    assert logs[0].escalated is False
