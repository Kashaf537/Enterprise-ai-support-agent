"""
Graph node: Save Memory

Last node before returning the final response. Persists this turn (user
message + assistant reply) to the conversation memory so the NEXT message
in this session sees it as history. Always runs last, regardless of which
path the graph took (clarify/escalate/normal), so every turn is recorded.
"""

from backend.memory.conversation_memory import memory
from backend.models.schemas import AgentState
from backend.utils.logger import logger


def save_memory_node(state: AgentState) -> dict:
    memory.save_turn(
        session_id=state.session_id,
        user_id=state.user_id,
        user_message=state.user_message,
        assistant_response=state.final_response,
    )
    logger.debug("[Node: save_memory] turn saved for session {}", state.session_id)
    return {"final_response": state.final_response}
