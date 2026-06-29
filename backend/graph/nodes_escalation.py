"""
Graph node: Confidence Check & Escalation

Implements the spec's exact rule:
  - confidence < 30%  -> automatically escalate to human support
  - confidence < 60%  -> ask a clarifying question instead of a possibly-
                         wrong confident-sounding answer
  - confidence >= 60% -> return the generated response as-is

This node runs the escalate_to_human TOOL directly (not via the LLM tool-
decision step) when auto-escalation triggers, since this is a deterministic
system rule, not something that needs LLM judgment.
"""

from backend.models.schemas import AgentState, ToolName
from backend.tools.tool_registry import execute_tool
from backend.utils.config import settings
from backend.utils.logger import logger

_CLARIFYING_TEMPLATE = (
    "I want to make sure I give you accurate information. Could you clarify a "
    "bit more — {follow_up}\n\nIn the meantime, here's what I found that might help:\n\n{partial_answer}"
)


def confidence_check_node(state: AgentState) -> dict:
    confidence = state.response_confidence

    if confidence < settings.escalate_threshold:
        logger.warning(
            "[Node: confidence_check] confidence={:.2f} < escalate_threshold={:.2f} -> auto-escalating",
            confidence, settings.escalate_threshold,
        )

        escalation_result = execute_tool(
            ToolName.ESCALATE_TO_HUMAN,
            session_id=state.session_id,
            user_id=state.user_id,
            reason=f"Low AI confidence ({confidence:.0%}) on: {state.user_message[:100]}",
            conversation_summary=state.user_message,
            category=state.intent.value if state.intent else "General Inquiry",
        )

        final_response = (
            f"{escalation_result['message']}\n\n"
            "In the meantime, here is my best attempt at an answer:\n\n"
            f"{state.final_response}"
        )

        return {
            "escalated": True,
            "needs_clarification": False,
            "final_response": final_response,
        }

    if confidence < settings.clarify_threshold:
        logger.info(
            "[Node: confidence_check] confidence={:.2f} < clarify_threshold={:.2f} -> asking for clarification",
            confidence, settings.clarify_threshold,
        )

        clarified_response = _CLARIFYING_TEMPLATE.format(
            follow_up="could you share more detail about what you're trying to do?",
            partial_answer=state.final_response,
        )

        return {
            "escalated": False,
            "needs_clarification": True,
            "final_response": clarified_response,
        }

    logger.debug("[Node: confidence_check] confidence={:.2f} -> returning response as-is", confidence)
    return {"escalated": False, "needs_clarification": False}
