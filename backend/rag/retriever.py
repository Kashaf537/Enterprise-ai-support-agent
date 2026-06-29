"""
High-level retrieval interface.

This module exists so the agent graph never has to know that ChromaDB or
Sentence Transformers exist — it just calls `retrieve(query)` and gets back
a clean list of RetrievedDocument objects. If we ever swap ChromaDB for
Pinecone or Weaviate, only vector_store.py changes; this file and everything
that calls it stay the same.
"""

from backend.models.schemas import RetrievedDocument
from backend.rag.vector_store import get_vector_store
from backend.utils.logger import logger


def retrieve(query: str, top_k: int | None = None) -> list[RetrievedDocument]:
    """
    Retrieves the top_k most semantically relevant knowledge base chunks
    for the given query.
    """
    store = get_vector_store()
    results = store.query(query, top_k=top_k)
    logger.debug("RAG retrieval for query='{}' returned {} documents", query, len(results))
    return results


def format_context_for_prompt(documents: list[RetrievedDocument]) -> str:
    """
    Formats retrieved documents into a single string suitable for injection
    into an LLM prompt, labeled by source so the model (and the user, if
    shown) can tell where each piece of information came from.
    """
    if not documents:
        return "No relevant documentation found."

    blocks = []
    for i, doc in enumerate(documents, start=1):
        blocks.append(
            f"[Source {i}: {doc.source} | relevance: {doc.similarity_score:.2f}]\n{doc.content}"
        )
    return "\n\n---\n\n".join(blocks)


def initialize_knowledge_base(force_rebuild: bool = False) -> None:
    """
    Convenience function to build/refresh the vector index. Call this once
    at application startup (FastAPI startup event) or via a standalone
    script after editing knowledge_base/*.md files.
    """
    store = get_vector_store()
    store.build_from_knowledge_base(force_rebuild=force_rebuild)
