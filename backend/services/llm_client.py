"""
Shared Groq LLM client.

Why one shared client instead of each agent creating its own?
Instantiating a ChatGroq client is cheap, but centralizing it here means:
  1. Model name / temperature / API key are configured in exactly one place
     (reading from our Settings object), so changing models later is a
     one-line change.
  2. Every agent module gets a consistently-configured client without
     duplicating langchain-groq setup code.

We use langchain-groq's ChatGroq class (rather than calling Groq's raw SDK
directly) because it gives us LangChain's standard `.invoke()` interface,
which is what the rest of the LangChain/LangGraph ecosystem expects — useful
if we later want to add LangChain features like output parsers or
streaming callbacks without changing call sites.
"""

from langchain_groq import ChatGroq

from backend.utils.config import settings


def get_llm(temperature: float | None = None) -> ChatGroq:
    """
    Returns a configured ChatGroq client.

    `temperature` can be overridden per-call — e.g. intent classification
    wants near-zero temperature (consistent, deterministic categorization),
    while response generation might want a touch more for natural-sounding
    text. Defaults to the global setting if not specified.
    """
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.llm_model,
        temperature=temperature if temperature is not None else settings.llm_temperature,
    )
