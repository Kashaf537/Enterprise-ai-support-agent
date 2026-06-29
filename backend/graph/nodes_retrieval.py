"""
Graph node: Knowledge Retrieval (RAG)

Decides whether retrieval is needed at all, and if so, runs it. We skip
retrieval when a tool already fully answered the request (e.g.
reset_password or calculate_refund produced a complete, self-contained
result) — there's no documentation lookup needed to explain "your refund is
$132.67", since the tool result IS the answer.
"""

from backend.models.schemas import AgentState, ToolName
from backend.rag.retriever import retrieve
from backend.utils.logger import logger

# Tools whose result is a complete, self-contained answer — retrieval adds
# little value here and just costs latency for no benefit.
_SELF_SUFFICIENT_TOOLS = {
    ToolName.RESET_PASSWORD,
    ToolName.CALCULATE_REFUND,
    ToolName.CHECK_TICKET_STATUS,
    ToolName.CREATE_SUPPORT_TICKET,
    ToolName.ESCALATE_TO_HUMAN,
}


def needs_knowledge_node(state: AgentState) -> dict:
    """
    Determines whether the retrieval step should run. This is a cheap,
    rule-based check (not an LLM call) since the logic is simple: if a
    self-sufficient tool already ran, skip retrieval; otherwise retrieve.
    """
    if state.tool_needed and state.tool_name in _SELF_SUFFICIENT_TOOLS and state.tool_result:
        logger.debug("[Node: needs_knowledge] tool result is self-sufficient, skipping retrieval")
        return {"needs_knowledge": False}

    return {"needs_knowledge": True}


def retrieve_documents_node(state: AgentState) -> dict:
    """
    Runs RAG retrieval against the user's message. Only reached when
    needs_knowledge_node decided retrieval is necessary (see the
    conditional edge in graph/workflow.py).
    """
    documents = retrieve(state.user_message)
    logger.debug("[Node: retrieve_documents] retrieved {} documents", len(documents))
    return {"retrieved_documents": documents}
