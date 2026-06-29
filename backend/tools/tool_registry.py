"""
Tool registry.

This is the single dispatch table mapping each ToolName enum value to its
actual Python function and a human-readable description. Two things consume
this registry:

  1. The agent's tool-decision node, which needs to describe available
     tools to the LLM (so it can decide which one — if any — to use).
  2. The agent's tool-execution node, which needs to actually CALL the
     chosen tool with the right arguments.

Centralizing this mapping means adding a 7th tool later is a two-step
process: write the tool function, then add one line here — nothing else in
the graph needs to change.
"""

from dataclasses import dataclass
from typing import Any, Callable

from backend.models.schemas import ToolName
from backend.tools.calculate_refund_tool import calculate_refund
from backend.tools.check_ticket_status_tool import check_ticket_status
from backend.tools.create_ticket_tool import create_support_ticket
from backend.tools.escalate_tool import escalate_to_human
from backend.tools.reset_password_tool import reset_password
from backend.tools.search_documentation_tool import search_documentation_as_text


@dataclass
class ToolSpec:
    name: ToolName
    description: str
    function: Callable[..., Any]


TOOL_REGISTRY: dict[ToolName, ToolSpec] = {
    ToolName.SEARCH_DOCUMENTATION: ToolSpec(
        name=ToolName.SEARCH_DOCUMENTATION,
        description=(
            "Search the TechNova Cloud knowledge base for relevant documentation. "
            "Use when the customer asks a question that documentation likely answers "
            "(how-to, policy, pricing, API usage)."
        ),
        function=search_documentation_as_text,
    ),
    ToolName.CREATE_SUPPORT_TICKET: ToolSpec(
        name=ToolName.CREATE_SUPPORT_TICKET,
        description=(
            "Create a support ticket for issues that need human follow-up or tracking, "
            "such as bug reports or unresolved technical problems."
        ),
        function=create_support_ticket,
    ),
    ToolName.CHECK_TICKET_STATUS: ToolSpec(
        name=ToolName.CHECK_TICKET_STATUS,
        description="Check the status of an existing support ticket by id, or list a customer's tickets.",
        function=check_ticket_status,
    ),
    ToolName.RESET_PASSWORD: ToolSpec(
        name=ToolName.RESET_PASSWORD,
        description="Trigger a password reset email when a customer can't log in or forgot their password.",
        function=reset_password,
    ),
    ToolName.CALCULATE_REFUND: ToolSpec(
        name=ToolName.CALCULATE_REFUND,
        description=(
            "Calculate a refund amount based on TechNova Cloud's refund policy "
            "(proration by days remaining in billing cycle, or outage credit)."
        ),
        function=calculate_refund,
    ),
    ToolName.ESCALATE_TO_HUMAN: ToolSpec(
        name=ToolName.ESCALATE_TO_HUMAN,
        description=(
            "Escalate the conversation to a human support agent — use when the customer "
            "explicitly asks for a human, the issue involves account security, or the AI "
            "cannot confidently resolve the issue."
        ),
        function=escalate_to_human,
    ),
}


def get_tool_descriptions_for_prompt() -> str:
    """
    Renders the registry as a numbered list for injection into the LLM
    prompt that decides which tool (if any) to use. This is how the LLM
    "knows" what tools exist, without us needing OpenAI-style function
    schemas (Groq's Llama 3.3 also supports native tool calling, but a
    plain-text description + JSON-output instruction is simpler to control
    and debug for a project like this).
    """
    lines = [f"- {spec.name.value}: {spec.description}" for spec in TOOL_REGISTRY.values()]
    return "\n".join(lines)


def execute_tool(tool_name: ToolName, **kwargs) -> Any:
    """
    Looks up and calls the function for `tool_name` with the given keyword
    arguments. Raises a clear error if the tool name isn't registered,
    rather than failing with a confusing KeyError deep in the graph.
    """
    if tool_name == ToolName.NONE:
        return None

    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise ValueError(f"Unknown tool: {tool_name}")

    return spec.function(**kwargs)
