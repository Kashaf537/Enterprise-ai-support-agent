"""
LangGraph workflow assembly.

This wires together every node into the exact flow described in the spec:

    User Question
        |
    Intent Detection
        |
    Need Tool? --(yes)--> Tool Execution --+
        |--(no)----------------------------+
        |
    Need Knowledge? --(yes)--> Retrieve Documents --+
        |--(no)---------------------------------------+
        |
    Generate Response
        |
    Confidence Check (clarify / escalate / pass-through)
        |
    Save Memory
        |
    Return Final Response

LangGraph's StateGraph works by:
  1. Registering each node function under a string name.
  2. Connecting nodes with edges (fixed: "always go from A to B") or
     conditional edges (a routing function decides which node comes next
     based on the current state).
  3. Compiling the graph into a runnable object whose .invoke(state) runs
     the whole workflow start to finish.

Note on LangGraph's state type: LangGraph traditionally uses a TypedDict
(or an Annotated dict with reducer functions) as its state schema. We use
our Pydantic AgentState directly — LangGraph supports Pydantic models as
state schemas natively (since langgraph>=0.2), giving us validation for
free without sacrificing the typed-node-update pattern.
"""

from langgraph.graph import END, StateGraph

from backend.graph.nodes_escalation import confidence_check_node
from backend.graph.nodes_intent import intent_detection_node
from backend.graph.nodes_memory import save_memory_node
from backend.graph.nodes_response import generate_response_node
from backend.graph.nodes_retrieval import needs_knowledge_node, retrieve_documents_node
from backend.graph.nodes_tools import tool_decision_node, tool_execution_node
from backend.models.schemas import AgentState


# ---------------------------------------------------------------------------
# Conditional edge routing functions
# ---------------------------------------------------------------------------

def route_after_tool_decision(state: AgentState) -> str:
    """Implements the 'Need Tool?' branch: if a tool was chosen, execute
    it; otherwise skip straight to the knowledge-need check.
    """
    return "tool_execution" if state.tool_needed else "needs_knowledge_check"


def route_after_knowledge_check(state: AgentState) -> str:
    """Implements the 'Need Knowledge?' branch: retrieve documents only if
    needs_knowledge_node decided they're necessary.
    """
    return "retrieve_documents" if state.needs_knowledge else "generate_response"


def build_support_agent_graph():
    """
    Constructs and compiles the LangGraph workflow. Called once at app
    startup; the compiled graph object is reused for every request (it's
    stateless between invocations — all per-conversation state lives in
    the AgentState object passed into .invoke(), not in the graph itself).
    """
    graph = StateGraph(AgentState)

    # --- Register nodes ---
    graph.add_node("intent_detection", intent_detection_node)
    graph.add_node("tool_decision", tool_decision_node)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("needs_knowledge_check", needs_knowledge_node)
    graph.add_node("retrieve_documents", retrieve_documents_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("confidence_check", confidence_check_node)
    graph.add_node("save_memory", save_memory_node)

    # --- Entry point ---
    graph.set_entry_point("intent_detection")

    # --- Fixed edges ---
    graph.add_edge("intent_detection", "tool_decision")

    # --- Conditional edge: Need Tool? ---
    graph.add_conditional_edges(
        "tool_decision",
        route_after_tool_decision,
        {
            "tool_execution": "tool_execution",
            "needs_knowledge_check": "needs_knowledge_check",
        },
    )
    # After executing a tool, we still check whether knowledge is ALSO
    # needed (e.g. a ticket was created, but the customer's broader
    # question still benefits from documentation context).
    graph.add_edge("tool_execution", "needs_knowledge_check")

    # --- Conditional edge: Need Knowledge? ---
    graph.add_conditional_edges(
        "needs_knowledge_check",
        route_after_knowledge_check,
        {
            "retrieve_documents": "retrieve_documents",
            "generate_response": "generate_response",
        },
    )
    graph.add_edge("retrieve_documents", "generate_response")

    # --- Remaining fixed edges ---
    graph.add_edge("generate_response", "confidence_check")
    graph.add_edge("confidence_check", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile()


# Module-level singleton — the compiled graph is stateless and safe to
# reuse across every request, so we build it once per process.
_compiled_graph = None


def get_support_agent_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_support_agent_graph()
    return _compiled_graph
