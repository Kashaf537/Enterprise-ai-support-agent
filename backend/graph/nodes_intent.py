"""
Graph node: Intent Detection

First node in the workflow. Classifies the incoming message and updates
state.intent / state.intent_confidence. Every downstream node depends on
this having run first.
"""

from backend.agents.intent_classifier import classify_intent
from backend.memory.conversation_memory import memory
from backend.models.schemas import AgentState
from backend.utils.logger import logger


def intent_detection_node(state: AgentState) -> dict:
    """
    LangGraph node convention: takes the full state, returns a dict of the
    fields this node wants to update. LangGraph merges this dict into the
    state object before passing it to the next node.
    """
    history_text = memory.format_history_for_prompt(state.chat_history)

    result = classify_intent(state.user_message, chat_history_text=history_text)

    logger.debug("[Node: intent_detection] {} (confidence={:.2f})", result.category.value, result.confidence)

    return {
        "intent": result.category,
        "intent_confidence": result.confidence,
    }
