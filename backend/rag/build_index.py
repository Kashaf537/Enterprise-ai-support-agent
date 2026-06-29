"""
Standalone script to (re)build the ChromaDB vector index from the
knowledge_base/ directory.

Run this:
  - Once, before first starting the app
  - Any time you add/edit/remove a .md file in knowledge_base/

Usage:
    python -m backend.rag.build_index            # build only if empty
    python -m backend.rag.build_index --rebuild   # wipe and rebuild from scratch
"""

import sys

from backend.rag.retriever import initialize_knowledge_base
from backend.utils.logger import logger


def main() -> None:
    force_rebuild = "--rebuild" in sys.argv
    logger.info("Building knowledge base index (force_rebuild={})", force_rebuild)
    initialize_knowledge_base(force_rebuild=force_rebuild)
    logger.info("Done.")


if __name__ == "__main__":
    main()
