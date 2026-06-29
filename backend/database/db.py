"""
Database engine and session factory.

Why a separate file for this?
The engine (connection to the actual SQLite file) should be created exactly
ONCE per process and shared everywhere. Sessions (a single unit-of-work /
transaction) should be created fresh per request/operation and closed
afterward. Keeping this in one place means every other module gets
consistent, correctly-configured database access without duplicating
connection logic.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.utils.config import settings
from backend.utils.logger import logger


class Base(DeclarativeBase):
    """Base class every ORM model inherits from. SQLAlchemy uses this to
    discover all table definitions when calling Base.metadata.create_all().
    """
    pass


def _ensure_sqlite_directory_exists(database_url: str) -> None:
    """
    SQLite creates the DATABASE FILE itself automatically, but it will NOT
    create missing parent directories — it just raises 'unable to open
    database file'. This matters specifically for the Docker setup, where
    docker-compose.yml points DATABASE_URL at /app/data/support_agent.db,
    a path that only exists because a volume is mounted there, not because
    anything has explicitly created it as a directory yet.
    """
    if not database_url.startswith("sqlite"):
        return

    # "sqlite:////app/data/support_agent.db" -> path component "/app/data/support_agent.db"
    db_path = urlparse(database_url).path
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory_exists(settings.database_url)

# `check_same_thread=False` is required for SQLite specifically because
# FastAPI may handle a request on a different thread than the one that
# created the connection; SQLite normally forbids cross-thread use.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=False,  # set True temporarily if you need to debug raw SQL
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """
    Creates all tables defined on Base's metadata if they don't already
    exist. Safe to call on every app startup — it's a no-op for tables that
    already exist.
    """
    # Importing models here (not at module top-level) ensures their table
    # definitions are registered on Base.metadata before create_all runs,
    # without creating a circular import between db.py and models.py.
    from backend.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized at {}", settings.database_url)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLAlchemy session and guarantees it's
    closed afterward, committing on success and rolling back on error.

    Usage:
        with get_db_session() as db:
            db.add(some_object)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency version of the above. FastAPI calls this generator,
    uses the yielded session for the duration of the request, then resumes
    the generator after the response is sent to close the session.

    Usage in an endpoint:
        @app.get("/tickets")
        def list_tickets(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
