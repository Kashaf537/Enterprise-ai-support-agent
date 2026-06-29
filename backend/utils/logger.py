"""
Centralized logging setup using loguru.

Why not just use print()?
  - print() statements give you no timestamps, no severity levels, and no way
    to turn them off in production without deleting code.
  - loguru gives structured, leveled logs (DEBUG/INFO/WARNING/ERROR) that write
    to both the console and a rotating log file, which is exactly what the
    project's "Logging" requirement (store timestamp, query, context, tool,
    response) needs as a foundation.

Usage elsewhere:
    from backend.utils.logger import logger
    logger.info("Agent received query: {}", query)
"""

import sys
from loguru import logger

from backend.utils.config import settings

# Remove the default handler so we can configure our own format/level.
logger.remove()

# Console sink — human-readable, colorized.
logger.add(
    sys.stdout,
    level=settings.log_level,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
)

# File sink — rotates at 10 MB, keeps 5 backups, useful for post-hoc debugging
# and feeds the "Logging" requirement of the spec (persistent audit trail).
logger.add(
    "logs/app.log",
    level="DEBUG",
    rotation="10 MB",
    retention=5,
    enqueue=True,  # thread-safe, important once FastAPI handles concurrent requests
)

__all__ = ["logger"]
