"""
Graph node: Generate Response

Synthesizes the final customer-facing reply from retrieved documents, tool
results, and conversation history, and computes the blended confidence
score used by the downstream confidence-check node.
"""

from backend.agents.response_generator import combine_confidence, generate_response
from backend.memory.conversation_memory import memory
from backend.models.schemas import AgentState
from backend.utils.logger import logger


def generate_response_node(state: AgentState) -> dict:
    history_text = memory.format_history_for_prompt(state.chat_history)

    result = generate_response(
        user_message=state.user_message,
        intent=state.intent,
        retrieved_documents=state.retrieved_documents,
        tool_result=state.tool_result,
        chat_history_text=history_text,
    )

    final_confidence = combine_confidence(result.confidence, state.retrieved_documents)

    logger.debug(
        "[Node: generate_response] llm_confidence={:.2f} blended_confidence={:.2f}",
        result.confidence, final_confidence,
    )

    return {
        "final_response": result.response,
        "response_confidence": final_confidence,
    }
