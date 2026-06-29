"""
Tool Decision Agent.

Given the customer's message, its classified intent, and conversation
history, decides whether a tool needs to be called and — if so — which one
and with what arguments.

This is the "should I act or just answer" reasoning step of the agent. Most
General Inquiry / FAQ-style questions need NO tool — they're answered
directly from RAG-retrieved documentation. Tools are for when the agent
needs to actually DO something (reset a password, create a ticket, do a
refund calculation) rather than just describe a policy.
"""

import json
import re

from pydantic import BaseModel, ValidationError

from backend.models.schemas import IntentCategory, ToolName
from backend.services.llm_client import get_llm
from backend.tools.tool_registry import get_tool_descriptions_for_prompt
from backend.utils.logger import logger

_SYSTEM_PROMPT = f"""You are a tool-routing system for TechNova Cloud's AI support agent.

Available tools:
{get_tool_descriptions_for_prompt()}

Given the customer's message and its classified intent, decide whether ANY \
tool should be called. Most general questions that can be answered from \
documentation do NOT need a tool — only choose a tool when the customer \
needs an ACTION performed (e.g. resetting a password, filing a ticket, \
calculating a refund, checking ticket status, or escalating).

Respond with ONLY a JSON object, no other text, no markdown fences:
{{"tool_needed": <true or false>, "tool_name": "<tool name or 'none'>", "extracted_args": {{}}, "reasoning": "<one short sentence>"}}

extracted_args should contain any values you can confidently extract from \
the message itself (e.g. an email address for reset_password, a ticket \
number for check_ticket_status). Leave it as an empty object if nothing \
relevant can be extracted — the calling code will fill in the rest.
"""


class ToolDecisionResult(BaseModel):
    tool_needed: bool
    tool_name: ToolName = ToolName.NONE
    extracted_args: dict = {}
    reasoning: str = ""


def _extract_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw_text!r}")
    return json.loads(match.group(0))


def decide_tool(
    user_message: str,
    intent: IntentCategory,
    chat_history_text: str = "",
) -> ToolDecisionResult:
    """
    Calls the LLM to decide whether a tool should be invoked for this
    message, and which one.
    """
    llm = get_llm(temperature=0.0)

    history_block = f"\nRecent conversation:\n{chat_history_text}\n" if chat_history_text else ""
    user_prompt = (
        f"{history_block}\n"
        f"Classified intent: {intent.value}\n"
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
        result = ToolDecisionResult(**parsed)
    except (ValueError, json.JSONDecodeError, ValidationError) as e:
        # Fail safe: no tool, just answer from documentation/LLM directly.
        # This is the safer default — incorrectly skipping a tool call is
        # far less harmful than incorrectly inventing one with bad args.
        logger.warning("Tool decision parse failure: {} | raw_text={!r}", e, raw_text)
        result = ToolDecisionResult(
            tool_needed=False, tool_name=ToolName.NONE,
            reasoning="Fallback due to tool-decision parse failure",
        )

    logger.info(
        "Tool decision for '{}': tool_needed={} tool_name={}",
        user_message[:60], result.tool_needed, result.tool_name.value,
    )
    return result
