"""
Tests for backend/models/schemas.py — confirms our Pydantic models validate
and reject data the way we expect. This matters because the whole system
relies on these models catching bad data EARLY (at the boundary) rather
than letting malformed data flow deep into the graph or database.
"""

import pytest
from pydantic import ValidationError

from backend.models.schemas import (
    AgentState,
    ChatRequest,
    IntentCategory,
    RetrievedDocument,
    ToolName,
)


def test_chat_request_requires_nonempty_message():
    with pytest.raises(ValidationError):
        ChatRequest(session_id="s1", user_id="u1", message="")


def test_chat_request_accepts_valid_input():
    req = ChatRequest(session_id="s1", user_id="u1", message="Hello")
    assert req.message == "Hello"
    assert req.user_id == "u1"


def test_chat_request_defaults_user_id_to_anonymous():
    req = ChatRequest(session_id="s1", message="Hello")
    assert req.user_id == "anonymous"


def test_retrieved_document_rejects_out_of_range_similarity():
    with pytest.raises(ValidationError):
        RetrievedDocument(content="x", source="a.md", category="a", similarity_score=1.5)


def test_retrieved_document_accepts_valid_score():
    doc = RetrievedDocument(content="x", source="a.md", category="a", similarity_score=0.87)
    assert doc.similarity_score == 0.87


def test_intent_category_rejects_invalid_value():
    with pytest.raises(ValueError):
        IntentCategory("Not A Real Category")


def test_intent_category_accepts_all_spec_categories():
    expected = {
        "Technical Issue", "Billing", "Refund", "Account",
        "API Support", "Feature Request", "General Inquiry",
    }
    actual = {c.value for c in IntentCategory}
    assert actual == expected


def test_agent_state_has_sensible_defaults():
    state = AgentState(session_id="s1", user_id="u1", user_message="hi")
    assert state.intent is None
    assert state.intent_confidence == 0.0
    assert state.tool_needed is False
    assert state.tool_name == ToolName.NONE
    assert state.retrieved_documents == []
    assert state.escalated is False
    assert state.chat_history == []


def test_agent_state_extracted_tool_args_is_independent_per_instance():
    """
    Regression test: mutable default fields (dict, list) in Pydantic models
    must use default_factory, or every instance would share the SAME dict
    object — a classic Python footgun. This confirms two AgentState
    instances don't accidentally share state.
    """
    state_a = AgentState(session_id="a", user_id="u", user_message="m")
    state_b = AgentState(session_id="b", user_id="u", user_message="m")

    state_a.extracted_tool_args["email"] = "a@example.com"

    assert "email" not in state_b.extracted_tool_args
