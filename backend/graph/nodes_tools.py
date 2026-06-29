"""
Graph nodes: Tool Decision and Tool Execution

Two separate nodes:
  1. tool_decision_node — asks the LLM whether a tool is needed, and which.
  2. tool_execution_node — actually calls the chosen tool with arguments,
     filling in any missing required arguments from state (session_id,
     user_id) that the LLM wouldn't have access to on its own.

Splitting decision from execution keeps each node's responsibility narrow:
the decision node is pure reasoning (no side effects), the execution node
is the only place that actually performs an action (DB write, simulated
email, etc).
"""

from backend.agents.tool_decision_agent import decide_tool
from backend.memory.conversation_memory import memory
from backend.models.schemas import AgentState, ToolName
from backend.tools.tool_registry import execute_tool
from backend.utils.logger import logger


def tool_decision_node(state: AgentState) -> dict:
    history_text = memory.format_history_for_prompt(state.chat_history)

    result = decide_tool(
        user_message=state.user_message,
        intent=state.intent,
        chat_history_text=history_text,
    )

    logger.debug(
        "[Node: tool_decision] tool_needed={} tool_name={}",
        result.tool_needed, result.tool_name.value,
    )

    return {
        "tool_needed": result.tool_needed,
        "tool_name": result.tool_name,
        "extracted_tool_args": result.extracted_args,
    }


def _build_tool_arguments(state: AgentState, extracted_args: dict) -> dict:
    """
    Merges LLM-extracted arguments with required context fields the LLM
    cannot know (session_id, user_id) and sensible defaults for fields the
    LLM didn't extract. This is where we bridge "what the LLM figured out
    from text" with "what the system already knows".
    """
    tool_name = state.tool_name

    if tool_name == ToolName.RESET_PASSWORD:
        return {"email": extracted_args.get("email", f"{state.user_id}@unknown.example")}

    if tool_name == ToolName.CREATE_SUPPORT_TICKET:
        return {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "subject": extracted_args.get("subject", state.user_message[:80]),
            "description": extracted_args.get("description", state.user_message),
            "category": state.intent.value if state.intent else "General Inquiry",
            "priority": extracted_args.get("priority", "medium"),
        }

    if tool_name == ToolName.CHECK_TICKET_STATUS:
        return {
            "session_id": state.session_id,
            "ticket_id": extracted_args.get("ticket_id"),
        }

    if tool_name == ToolName.CALCULATE_REFUND:
        return {
            "amount_charged": extracted_args.get("amount_charged", 0.0),
            "days_remaining_in_cycle": extracted_args.get("days_remaining_in_cycle", 0),
            "total_days_in_cycle": extracted_args.get("total_days_in_cycle", 30),
            "reason": extracted_args.get("reason", "customer_request"),
            "outage_hours": extracted_args.get("outage_hours", 0.0),
        }

    if tool_name == ToolName.ESCALATE_TO_HUMAN:
        return {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "reason": extracted_args.get("reason", "Low confidence / customer request"),
            "conversation_summary": extracted_args.get("conversation_summary", state.user_message),
            "category": state.intent.value if state.intent else "General Inquiry",
        }

    if tool_name == ToolName.SEARCH_DOCUMENTATION:
        return {"query": extracted_args.get("query", state.user_message)}

    return {}


def tool_execution_node(state: AgentState) -> dict:
    """
    Executes the tool chosen by tool_decision_node, if any. Reads
    state.extracted_tool_args (populated by tool_decision_node) and merges
    it with required context fields the LLM cannot know on its own
    (session_id, user_id).
    """
    if not state.tool_needed or state.tool_name == ToolName.NONE:
        return {"tool_result": None}

    extracted_args = state.extracted_tool_args or {}
    args = _build_tool_arguments(state, extracted_args)

    try:
        result = execute_tool(state.tool_name, **args)
        logger.info("[Node: tool_execution] {} executed -> {}", state.tool_name.value, result)
        return {"tool_result": str(result)}
    except Exception as e:
        # A failed tool call shouldn't crash the whole conversation — log
        # it and let response generation explain that the action couldn't
        # be completed, which is far better UX than a 500 error.
        logger.error("[Node: tool_execution] {} failed: {}", state.tool_name.value, e)
        return {"tool_result": f"Tool execution failed: {e}"}
