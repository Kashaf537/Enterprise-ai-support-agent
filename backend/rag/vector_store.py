"""
Vector store layer: wraps Sentence Transformers (embedding model) and
ChromaDB (vector database) behind a simple class with `build()` and
`query()` methods.

Why Sentence Transformers?
It converts text into a fixed-length numeric vector ("embedding") such that
semantically similar sentences end up close together in vector space. We use
`all-MiniLM-L6-v2` — small (~80MB), fast on CPU, and good enough quality for
a support-doc RAG use case. This is exactly what the spec asks for.

Why ChromaDB?
It's a lightweight, embedded (no separate server needed) vector database
that stores embeddings + metadata and lets us run a similarity search
("give me the k closest vectors to this query vector") in a couple of lines.
It persists to disk, so we only need to build the index once.
"""

from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from backend.models.schemas import RetrievedDocument
from backend.rag.document_loader import DocumentChunk, load_knowledge_base
from backend.utils.config import settings
from backend.utils.logger import logger

COLLECTION_NAME = "technova_knowledge_base"


class VectorStore:
    """
    Thin wrapper around a single ChromaDB collection.

    Usage:
        store = VectorStore()
        store.build_from_knowledge_base()   # run once (or whenever docs change)
        results = store.query("how do refunds work?", top_k=4)
    """

    def __init__(self) -> None:
        # PersistentClient writes the index to disk at chroma_persist_dir,
        # so embeddings survive process restarts and don't need rebuilding
        # every time the app starts.
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

        # ChromaDB's SentenceTransformerEmbeddingFunction handles loading the
        # model and embedding text automatically whenever we add() or
        # query() — we never have to call the model ourselves.
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )

        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},  # cosine similarity for sentence embeddings
        )

    def is_empty(self) -> bool:
        return self._collection.count() == 0

    def build_from_knowledge_base(self, force_rebuild: bool = False) -> None:
        """
        Loads, chunks, and embeds every document in the knowledge base
        directory, then upserts them into the ChromaDB collection.

        force_rebuild=True wipes the existing collection first — use this
        after editing knowledge base files so stale chunks don't linger.
        """
        if force_rebuild:
            logger.info("Force rebuild requested — clearing existing collection")
            self._client.delete_collection(COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
        elif not self.is_empty():
            logger.info("Vector store already populated ({} chunks) — skipping rebuild", self._collection.count())
            return

        chunks: list[DocumentChunk] = load_knowledge_base(settings.knowledge_base_dir)
        if not chunks:
            logger.warning("No chunks to index — knowledge base appears empty")
            return

        # ChromaDB's add() embeds `documents` automatically using our
        # embedding_function — we just supply raw text + metadata + ids.
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.content for c in chunks],
            metadatas=[{"source": c.source, "category": c.category} for c in chunks],
        )
        logger.info("Indexed {} chunks into ChromaDB collection '{}'", len(chunks), COLLECTION_NAME)

    def query(self, query_text: str, top_k: int | None = None) -> list[RetrievedDocument]:
        """
        Embeds `query_text` and returns the top_k most similar chunks as
        RetrievedDocument objects (the shape the rest of the app expects).
        """
        top_k = top_k or settings.rag_top_k

        if self.is_empty():
            logger.warning("Query attempted on empty vector store")
            return []

        results = self._collection.query(
            query_texts=[query_text],
            n_results=top_k,
        )

        documents: list[RetrievedDocument] = []
        # Chroma returns parallel lists nested one level for batch queries;
        # since we sent exactly one query_text, everything is at index [0].
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc_text, meta, distance in zip(docs, metadatas, distances):
            # Chroma returns cosine *distance* (0 = identical, 2 = opposite).
            # We convert to a 0-1 *similarity* score, which is more intuitive
            # for confidence scoring and for display in the UI.
            similarity = max(0.0, 1.0 - (distance / 2.0))
            documents.append(
                RetrievedDocument(
                    content=doc_text,
                    source=meta.get("source", "unknown"),
                    category=meta.get("category", "unknown"),
                    similarity_score=round(similarity, 4),
                )
            )

        return documents


# Module-level singleton so the (relatively expensive) embedding model is
# loaded into memory only once per process, and every caller shares the
# same ChromaDB connection.
_vector_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
