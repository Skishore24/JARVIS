"""
memory/database.py
------------------
SQLAlchemy engine + Base setup for JARVIS persistence layer.
Provides a session factory and declarative base for all ORM models.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base for all JARVIS ORM models."""
    pass


def _create_db_engine():
    """Create and configure the SQLAlchemy engine."""
    engine = create_engine(
        config.DATABASE_URL,
        connect_args={"check_same_thread": False},  # required for SQLite + threads
        echo=False,
    )

    # Enable WAL mode for better concurrent reads on SQLite
    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    logger.info("Database engine created: %s", config.DATABASE_URL)
    return engine


# Module-level singletons
_engine = _create_db_engine()
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables (safe to call multiple times — uses CREATE IF NOT EXISTS)."""
    # Import models so their metadata is registered before create_all
    from memory.conversation import ConversationMessage, ConversationSession  # noqa: F401

    Base.metadata.create_all(bind=_engine)
    logger.info("Database tables initialised.")


init_database = init_db


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager that provides a SQLAlchemy session and
    automatically commits on success or rolls back on error.

    Usage:
        with get_session() as session:
            session.add(obj)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    """Return the module-level engine (for migration tools etc.)."""
    return _engine
