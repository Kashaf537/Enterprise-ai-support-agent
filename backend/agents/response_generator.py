"""
Response Generation Agent.

The final "thinking" step: synthesizes retrieved documentation, any tool
result, and conversation history into a natural-language reply, and assigns
a confidence score to that reply.

Why ask the LLM to self-rate confidence, rather than deriving confidence
purely from RAG similarity scores?
RAG similarity alone doesn't capture everything — e.g. a tool might have
already fully resolved the issue (high confidence, regardless of retrieval
score), or the retrieved docs might be only tangentially related to a
nuanced question (low confidence, even with a decent similarity score). We
combine both signals: retrieval quality is folded into the prompt context,
and the LLM produces a final self-assessed confidence number, which we then
blend with retrieval similarity for a more robust final figure (see
combine_confidence below).
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from backend.models.schemas import IntentCategory, RetrievedDocument
from backend.rag.retriever import format_context_for_prompt
from backend.services.llm_client import get_llm
from backend.utils.logger import logger

_SYSTEM_PROMPT = """You are TechNova Cloud's AI customer support agent. You are professional, \
concise, and helpful. Answer using ONLY the provided documentation context and tool \
result (if any) — do not invent policies, prices, or facts not present in the context.

If the context doesn't contain enough information to fully answer the question, \
say so honestly rather than guessing, and lower your confidence score accordingly.

Respond with ONLY a JSON object, no other text, no markdown fences:
{"response": "<your reply to the customer, written naturally>", "confidence": <float 0.0-1.0>, "reasoning": "<one short sentence on why this confidence level>"}

confidence reflects how well-grounded and complete your answer is:
- 0.8-1.0: directly and fully answered by the provided context/tool result
- 0.5-0.79: partially answered, or answered with some inference beyond the context
- 0.0-0.49: context is insufficient, off-topic, or you are largely guessing
"""


class ResponseGenerationResult(BaseModel):
    response: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""


def _extract_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw_text!r}")
    return json.loads(match.group(0))


def generate_response(
    user_message: str,
    intent: IntentCategory,
    retrieved_documents: list[RetrievedDocument],
    tool_result: str | None,
    chat_history_text: str = "",
) -> ResponseGenerationResult:
    """
    Generates the final customer-facing response and a self-assessed
    confidence score, grounded in retrieved docs + tool result.
    """
    llm = get_llm(temperature=0.3)  # slightly higher — natural-sounding prose

    context_block = format_context_for_prompt(retrieved_documents)
    tool_block = f"\nTool result: {tool_result}\n" if tool_result else ""
    history_block = f"\nRecent conversation:\n{chat_history_text}\n" if chat_history_text else ""

    user_prompt = (
        f"{history_block}\n"
        f"Classified intent: {intent.value}\n\n"
        f"Documentation context:\n{context_block}\n"
        f"{tool_block}\n"
        f'Customer message: "{user_message}"'
    )

    messages = [
        ("system", _SYSTEM_PROMPT),
        ("human", user_prompt),
    ]

    response = llm.invoke(messages)
    raw_text = response.content

    try:
        parsed = _extract_json(raw_text)
        result = ResponseGenerationResult(**parsed)
    except (ValueError, json.JSONDecodeError, ValidationError) as e:
        # If generation itself fails to parse, fall back to a low-confidence
        # generic message rather than crashing — this naturally triggers
        # the escalation path downstream, which is the safe outcome when
        # something has gone wrong in the pipeline.
        logger.error("Response generation parse failure: {} | raw_text={!r}", e, raw_text)
        result = ResponseGenerationResult(
            response=(
                "I'm having trouble generating a confident answer right now. "
                "Let me connect you with a human agent who can help further."
            ),
            confidence=0.0,
            reasoning="Fallback due to response generation parse failure",
        )

    logger.info(
        "Response generated for '{}' with confidence={:.2f}",
        user_message[:60], result.confidence,
    )
    return result


def combine_confidence(llm_confidence: float, retrieved_documents: list[RetrievedDocument]) -> float:
    """
    Blends the LLM's self-assessed confidence with the average retrieval
    similarity score, weighted toward the LLM's judgment but pulled down
    when retrieval was weak even if the LLM sounded confident.

    Why blend rather than trust the LLM alone?
    LLMs can be overconfident in free-text self-assessment. Anchoring part
    of the score to a hard, measurable signal (retrieval similarity) makes
    the final confidence number more trustworthy for driving the
    clarify/escalate decisions in the spec.
    """
    if not retrieved_documents:
        # No documents retrieved at all (e.g. a pure tool-result answer) —
        # trust the LLM's self-assessment alone.
        return llm_confidence

    avg_similarity = sum(d.similarity_score for d in retrieved_documents) / len(retrieved_documents)

    # 70% weight on LLM self-assessment, 30% on retrieval grounding.
    combined = (0.7 * llm_confidence) + (0.3 * avg_similarity)
    return round(min(1.0, max(0.0, combined)), 4)
