"""
Tool: search_documentation

Wraps the RAG retriever (backend/rag/retriever.py) as a callable "tool" the
agent can invoke. In practice this tool is usually called implicitly by the
graph's retrieval node rather than via explicit LLM tool-calling, but it's
exposed here in the same shape as the other tools so it can ALSO be invoked
directly by the agent's tool-decision step when a user explicitly asks
something like "search the docs for X".
"""

from pydantic import BaseModel, Field

from backend.models.schemas import RetrievedDocument
from backend.rag.retriever import retrieve
from backend.utils.logger import logger


class SearchDocumentationInput(BaseModel):
    query: str = Field(..., description="The search query to look up in the knowledge base")
    top_k: int = Field(default=4, description="Number of results to return")


def search_documentation(query: str, top_k: int = 4) -> list[RetrievedDocument]:
    """
    Searches the TechNova Cloud knowledge base (FAQ, API docs, pricing,
    troubleshooting, refund policy, company policies) for content
    semantically relevant to `query`.

    Returns a list of RetrievedDocument, each with the source file,
    category, and a similarity score.
    """
    logger.info("Tool called: search_documentation(query='{}', top_k={})", query, top_k)
    results = retrieve(query, top_k=top_k)
    return results


def search_documentation_as_text(query: str, top_k: int = 4) -> str:
    """
    Convenience wrapper that returns a plain text summary instead of
    structured objects — useful when the LLM itself needs the tool's result
    formatted directly into a follow-up prompt (LLM tool-calling APIs expect
    a string tool result).
    """
    results = search_documentation(query, top_k=top_k)
    if not results:
        return "No relevant documentation found."

    lines = [f"- [{r.source}] {r.content[:200]}..." for r in results]
    return "\n".join(lines)
