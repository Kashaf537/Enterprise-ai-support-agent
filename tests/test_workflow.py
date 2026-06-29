"""
Tests for backend/graph/workflow.py.

These tests mock every LLM-calling function (intent classification, tool
decision, response generation) and the RAG retriever, so they run fully
offline and deterministically — no Groq API key or network access needed,
and no flakiness from real model output varying between runs.

What's actually under test here is the GRAPH WIRING ITSELF: do the
conditional edges route to the right node given the state at that point,
does state merge correctly across nodes, and do the escalate/clarify/
pass-through branches in confidence_check_node produce the right outcome.
"""

import pytest

from backend.models.schemas import AgentState, IntentCategory, RetrievedDocument, ToolName


@pytest.fixture()
def mocked_graph(monkeypatch):
    """
    Builds a fresh compiled graph with every LLM/RAG dependency replaced by
    a configurable fake. Returns a dict of setter functions so each test
    can control exactly what each mocked component returns, plus the
    compiled graph itself.
    """
    import backend.agents.intent_classifier as intent_mod
    import backend.agents.tool_decision_agent as tool_mod
    import backend.agents.response_generator as resp_mod
    import backend.graph.nodes_intent as n_intent
    import backend.graph.nodes_tools as n_tools
    import backend.graph.nodes_retrieval as n_retrieval
    import backend.graph.nodes_response as n_response

    state = {
        "intent_category": IntentCategory.GENERAL_INQUIRY,
        "intent_confidence": 0.9,
        "tool_needed": False,
        "tool_name": ToolName.NONE,
        "extracted_args": {},
        "retrieved_docs": [],
        "response_text": "default mocked response",
        "response_confidence": 0.9,
    }

    def fake_classify_intent(user_message, chat_history_text=""):
        return intent_mod.IntentClassificationResult(
            category=state["intent_category"], confidence=state["intent_confidence"], reasoning="mocked"
        )

    def fake_decide_tool(user_message, intent, chat_history_text=""):
        return tool_mod.ToolDecisionResult(
            tool_needed=state["tool_needed"], tool_name=state["tool_name"],
            extracted_args=state["extracted_args"], reasoning="mocked",
        )

    def fake_retrieve(query, top_k=None):
        return state["retrieved_docs"]

    def fake_generate_response(user_message, intent, retrieved_documents, tool_result, chat_history_text=""):
        return resp_mod.ResponseGenerationResult(
            response=state["response_text"], confidence=state["response_confidence"], reasoning="mocked"
        )

    monkeypatch.setattr(n_intent, "classify_intent", fake_classify_intent)
    monkeypatch.setattr(n_tools, "decide_tool", fake_decide_tool)
    monkeypatch.setattr(n_retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(n_response, "generate_response", fake_generate_response)

    # Also patch the tool EXECUTION dispatch so a "tool needed" test doesn't
    # require a real database/email side effect — we only care that the
    # graph routes to tool_execution and that its result flows downstream.
    import backend.graph.nodes_tools as nt

    def fake_execute_tool(tool_name, **kwargs):
        if tool_name == ToolName.RESET_PASSWORD:
            return {"message": f"Reset link sent to {kwargs.get('email')}"}
        return {"message": "mocked tool result"}

    monkeypatch.setattr(nt, "execute_tool", fake_execute_tool)

    # The escalation node also calls execute_tool directly for ESCALATE_TO_HUMAN.
    import backend.graph.nodes_escalation as ne
    monkeypatch.setattr(
        ne, "execute_tool",
        lambda tool_name, **kwargs: {"message": "Escalated.", "ticket_id": 1},
    )

    # Avoid real DB writes in save_memory_node for these pure-routing tests.
    import backend.graph.nodes_memory as nm
    monkeypatch.setattr(nm.memory, "save_turn", lambda **kwargs: None)

    from backend.graph.workflow import build_support_agent_graph
    graph = build_support_agent_graph()

    return {"graph": graph, "state": state}


def _run(mocked_graph, message: str, **overrides) -> dict:
    mocked_graph["state"].update(overrides)
    initial = AgentState(session_id="test-sess", user_id="test-user", user_message=message)
    return mocked_graph["graph"].invoke(initial)


class TestNoToolPath:
    def test_high_confidence_passes_through_without_escalation_or_clarification(self, mocked_graph):
        result = _run(
            mocked_graph, "What is TechNova Cloud?",
            tool_needed=False, response_confidence=0.9,
            retrieved_docs=[RetrievedDocument(content="x", source="faq.md", category="faq", similarity_score=0.9)],
        )
        assert result["tool_needed"] is False
        assert result["escalated"] is False
        assert result["needs_clarification"] is False
        assert result["final_response"] == "default mocked response"


class TestToolPath:
    def test_tool_needed_routes_through_tool_execution(self, mocked_graph):
        result = _run(
            mocked_graph, "I forgot my password",
            tool_needed=True, tool_name=ToolName.RESET_PASSWORD,
            extracted_args={"email": "bob@example.com"},
        )
        assert result["tool_needed"] is True
        assert result["tool_name"] == ToolName.RESET_PASSWORD
        assert "bob@example.com" in result["tool_result"]

    def test_self_sufficient_tool_skips_knowledge_retrieval(self, mocked_graph):
        result = _run(
            mocked_graph, "Calculate my refund",
            tool_needed=True, tool_name=ToolName.CALCULATE_REFUND,
        )
        assert result["needs_knowledge"] is False


class TestConfidenceRouting:
    def test_confidence_above_clarify_threshold_passes_through(self, mocked_graph):
        result = _run(mocked_graph, "test message", response_confidence=0.75)
        assert result["escalated"] is False
        assert result["needs_clarification"] is False

    def test_confidence_between_thresholds_triggers_clarification(self, mocked_graph):
        result = _run(mocked_graph, "test message", response_confidence=0.45)
        assert result["needs_clarification"] is True
        assert result["escalated"] is False

    def test_confidence_below_escalate_threshold_triggers_escalation(self, mocked_graph):
        result = _run(mocked_graph, "test message", response_confidence=0.15)
        assert result["escalated"] is True
        assert result["needs_clarification"] is False
        assert "Escalated." in result["final_response"]

    def test_confidence_exactly_at_clarify_threshold_does_not_clarify(self, mocked_graph):
        # The spec says "below 60%" triggers clarification, so exactly 0.60
        # should NOT trigger it — boundary behavior matters here.
        result = _run(mocked_graph, "test message", response_confidence=0.60)
        assert result["needs_clarification"] is False

    def test_confidence_exactly_at_escalate_threshold_does_not_escalate(self, mocked_graph):
        result = _run(mocked_graph, "test message", response_confidence=0.30)
        assert result["escalated"] is False
