"""
Intent Classification Agent.

Classifies a customer's message into one of the IntentCategory enum values,
with a confidence score (0.0-1.0). This is the first real "thinking" step
in the agent graph — everything downstream (whether to retrieve docs, which
tool to consider, how to phrase the response) depends on knowing what kind
of request this is.

Approach: prompt the LLM to respond with ONLY a JSON object, then parse and
validate that JSON into a Pydantic model. This is more reliable than asking
the LLM to "just say the category" in free text, because free text is much
harder to parse consistently (e.g. "I think this is Billing" vs "Billing"
vs "billing related question").
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from backend.models.schemas import IntentCategory
from backend.services.llm_client import get_llm
from backend.utils.logger import logger

_VALID_CATEGORIES = [c.value for c in IntentCategory]

_SYSTEM_PROMPT = f"""You are an intent classification system for TechNova Cloud, a SaaS platform.

Classify the customer's message into EXACTLY ONE of these categories:
{chr(10).join(f"- {c}" for c in _VALID_CATEGORIES)}

Respond with ONLY a JSON object in this exact format, with no other text, \
no markdown code fences, no explanation:
{{"category": "<one of the categories above>", "confidence": <float between 0.0 and 1.0>, "reasoning": "<one short sentence>"}}

Guidelines:
- "Technical Issue": bugs, errors, deployments failing, something broken
- "Billing": payment methods, invoices, subscription charges, plan changes
- "Refund": explicitly asking for money back
- "Account": login, password, team members, account settings/deletion
- "API Support": API keys, endpoints, rate limits, SDK questions
- "Feature Request": asking for new functionality that doesn't exist yet
- "General Inquiry": anything that doesn't clearly fit above, including greetings

confidence should reflect how clearly the message matches the category — \
a vague or ambiguous message should get a LOWER confidence score (e.g. 0.4-0.6), \
not a falsely high one.
"""


class IntentClassificationResult(BaseModel):
    category: IntentCategory
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""


def _extract_json(raw_text: str) -> dict:
    """
    LLMs occasionally wrap JSON in markdown code fences or add stray text
    even when instructed not to. This extracts the first {...} block found,
    which is more robust than assuming the entire response is valid JSON.
    """
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw_text!r}")
    return json.loads(match.group(0))


def classify_intent(user_message: str, chat_history_text: str = "") -> IntentClassificationResult:
    """
    Calls the LLM to classify `user_message` into an IntentCategory.

    chat_history_text (optional) provides conversation context — e.g. if the
    customer previously said "I was charged twice" and now says "how do I
    get that back", history helps the classifier correctly identify this as
    Refund rather than General Inquiry.
    """
    llm = get_llm(temperature=0.0)  # deterministic — we want consistent categorization

    history_block = f"\nRecent conversation:\n{chat_history_text}\n" if chat_history_text else ""
    user_prompt = f"{history_block}\nCustomer message: \"{user_message}\""

    messages = [
        ("system", _SYSTEM_PROMPT),
        ("human", user_prompt),
    ]

    response = llm.invoke(messages)
    raw_text = response.content

    try:
        parsed = _extract_json(raw_text)
        result = IntentClassificationResult(**parsed)
    except (ValueError, json.JSONDecodeError, ValidationError) as e:
        # If the LLM ever produces malformed output, we fail safe rather
        # than crashing the whole request: default to General Inquiry with
        # low confidence, which naturally routes toward clarification/
        # escalation downstream instead of a confident wrong answer.
        logger.warning("Intent classification parse failure: {} | raw_text={!r}", e, raw_text)
        result = IntentClassificationResult(
            category=IntentCategory.GENERAL_INQUIRY,
            confidence=0.3,
            reasoning="Fallback due to classification parse failure",
        )

    logger.info(
        "Intent classified: '{}' -> {} (confidence={:.2f})",
        user_message[:60], result.category.value, result.confidence,
    )
    return result
