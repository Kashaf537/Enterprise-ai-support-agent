"""
Shared pytest fixtures.

The most important fixture here is `db_session`, which gives every test an
isolated, in-memory SQLite database — created fresh and destroyed after
each test function. This means tests never interact with your real
support_agent.db file, never leak state between tests, and run fast (no
disk I/O).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base


@pytest.fixture()
def db_session():
    """
    Yields a SQLAlchemy session backed by a fresh in-memory SQLite database
    for a single test. Tables are created before the test runs and the
    whole engine (and thus all data) is discarded afterward.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestSessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        engine.dispose()
