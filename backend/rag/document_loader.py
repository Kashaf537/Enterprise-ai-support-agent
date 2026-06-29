"""
Loads markdown files from the knowledge base directory and splits them into
overlapping text chunks suitable for embedding.

Why chunk at all?
Embedding an entire 2000-word document as a single vector loses precision —
the vector becomes an average of many unrelated ideas, so semantic search
against it is fuzzy. Instead we split each document into smaller chunks
(roughly paragraph-sized) so each vector represents one coherent idea, which
makes retrieval far more accurate.

Why overlap chunks?
If a chunk boundary falls in the middle of an important sentence, splitting
loses context. A small overlap (e.g. 50 characters) means the end of one
chunk re-appears at the start of the next, so no idea is fully severed.
"""

from dataclasses import dataclass
from pathlib import Path

from backend.utils.logger import logger


@dataclass
class DocumentChunk:
    """A single chunk of text ready to be embedded, with metadata describing
    where it came from. Metadata is what lets us show the user "this answer
    came from refund_policy.md" later in the UI.
    """
    content: str
    source: str       # filename, e.g. "faq.md"
    category: str     # derived from filename, e.g. "faq"
    chunk_id: str      # unique id: "<source>::chunk_<n>"


def _category_from_filename(filename: str) -> str:
    """'troubleshooting_guide.md' -> 'troubleshooting_guide'."""
    return Path(filename).stem


def split_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    Splits text into overlapping chunks, preferring to break on paragraph
    boundaries (double newlines) so we don't cut sentences in half whenever
    avoidable.

    This is a simple, dependency-light splitter. (LangChain's
    RecursiveCharacterTextSplitter does the same job and can be swapped in
    here if you want more nuanced separators — see commented alternative
    below.)
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # If adding this paragraph would overflow the chunk size, flush
        # the current chunk and start a new one (carrying over the tail
        # of the previous chunk as overlap for context continuity).
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            overlap_tail = current[-chunk_overlap:] if chunk_overlap else ""
            current = overlap_tail + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks

    # --- Alternative using LangChain (equivalent, more configurable) ---
    # from langchain.text_splitter import RecursiveCharacterTextSplitter
    # splitter = RecursiveCharacterTextSplitter(
    #     chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    #     separators=["\n\n", "\n", ". ", " "],
    # )
    # return splitter.split_text(text)


def load_knowledge_base(directory: str) -> list[DocumentChunk]:
    """
    Reads every .md file in `directory`, chunks it, and returns a flat list
    of DocumentChunk objects ready for embedding.
    """
    kb_dir = Path(directory)
    if not kb_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {directory}")

    all_chunks: list[DocumentChunk] = []
    md_files = sorted(kb_dir.glob("*.md"))

    if not md_files:
        logger.warning("No .md files found in knowledge base directory: {}", directory)

    for file_path in md_files:
        text = file_path.read_text(encoding="utf-8")
        raw_chunks = split_into_chunks(text)
        category = _category_from_filename(file_path.name)

        for i, chunk_text in enumerate(raw_chunks):
            all_chunks.append(
                DocumentChunk(
                    content=chunk_text,
                    source=file_path.name,
                    category=category,
                    chunk_id=f"{file_path.stem}::chunk_{i}",
                )
            )

        logger.info("Loaded {} chunks from {}", len(raw_chunks), file_path.name)

    logger.info("Knowledge base loaded: {} total chunks from {} files", len(all_chunks), len(md_files))
    return all_chunks
