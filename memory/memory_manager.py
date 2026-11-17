"""
memory/memory_manager.py
------------------------
High-level CRUD API for JARVIS memory:
  - Session management (create, list, delete)
  - Message storage and retrieval
  - Conversation history formatting for the LLM
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import delete, select

import config
from memory.database import get_session, init_db
from memory.conversation import ConversationMessage, ConversationSession

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Provides all memory operations for the JARVIS assistant.

    All DB interactions go through the ``get_session()`` context manager
    to ensure proper commit/rollback handling.
    """

    def __init__(self) -> None:
        # Ensure DB tables exist on first run
        init_db()
        logger.info("MemoryManager initialised.")

    # ── Session Management ────────────────────────────────────────────────────

    def new_session(self, title: str | None = None, model: str | None = None) -> str:
        """
        Create a new conversation session and return its ID.

        Args:
            title: Optional human-readable session label.
            model: The LLM model name used in this session.

        Returns:
            The new session's UUID string.
        """
        session_id = str(uuid.uuid4())
        with get_session() as db:
            session = ConversationSession(
                id=session_id,
                title=title or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                model_used=model or config.OLLAMA_DEFAULT_MODEL,
            )
            db.add(session)
        logger.info("New session created: %s", session_id)
        return session_id

    def list_sessions(self, limit: int = 20) -> list[ConversationSession]:
        """Return the most recent *limit* sessions, newest first."""
        with get_session() as db:
            stmt = (
                select(ConversationSession)
                .order_by(ConversationSession.created_at.desc())
                .limit(limit)
            )
            return list(db.scalars(stmt).all())

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages (cascade).

        Returns:
            True if the session existed and was deleted, False otherwise.
        """
        with get_session() as db:
            stmt = select(ConversationSession).where(ConversationSession.id == session_id)
            session = db.scalars(stmt).first()
            if session is None:
                logger.warning("delete_session: session %s not found.", session_id)
                return False
            db.delete(session)
        logger.info("Deleted session: %s", session_id)
        return True

    # ── Message Operations ────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        tool_result: str | None = None,
    ) -> int:
        """
        Append a message to a session.

        Args:
            session_id:  Target session UUID.
            role:        "user", "assistant", or "system".
            content:     Message text.
            intent:      Optional tool intent name (e.g. "SYSTEM_MONITOR").
            tool_result: Optional tool execution result.

        Returns:
            The new message's integer ID.
        """
        with get_session() as db:
            msg = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                intent=intent,
                tool_result=tool_result,
            )
            db.add(msg)
            db.flush()  # assigns msg.id before commit
            msg_id = msg.id
        logger.debug("Message %d added to session %s [%s].", msg_id, session_id, role)
        return msg_id

    def get_recent_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[ConversationMessage]:
        """
        Return the most recent *limit* messages for a session, oldest first.

        Args:
            session_id: Target session UUID.
            limit:      Max messages to return (defaults to config value).

        Returns:
            List of ConversationMessage objects in chronological order.
        """
        cap = limit or config.MAX_CONVERSATION_HISTORY
        with get_session() as db:
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.timestamp.desc())
                .limit(cap)
            )
            rows = list(db.scalars(stmt).all())
        # Return in chronological order (oldest first)
        rows.reverse()
        return rows

    def get_all_messages(self, session_id: str) -> list[ConversationMessage]:
        """Return every message in a session, oldest first."""
        with get_session() as db:
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.timestamp)
            )
            return list(db.scalars(stmt).all())

    def delete_message(self, message_id: int) -> bool:
        """Delete a single message by its integer ID."""
        with get_session() as db:
            stmt = select(ConversationMessage).where(ConversationMessage.id == message_id)
            msg = db.scalars(stmt).first()
            if msg is None:
                return False
            db.delete(msg)
        return True

    def clear_session_messages(self, session_id: str) -> int:
        """
        Delete all messages in a session without deleting the session itself.

        Returns:
            Number of messages deleted.
        """
        with get_session() as db:
            stmt = (
                delete(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
            )
            result = db.execute(stmt)
        count: int = result.rowcount
        logger.info("Cleared %d messages from session %s.", count, session_id)
        return count

    # ── Search ────────────────────────────────────────────────────────────────

    def search_messages(self, query: str, limit: int = 20) -> list[ConversationMessage]:
        """
        Simple substring search across all message content.

        Args:
            query: Text to search for (case-insensitive).
            limit: Max results.

        Returns:
            Matching messages, newest first.
        """
        with get_session() as db:
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.content.ilike(f"%{query}%"))
                .order_by(ConversationMessage.timestamp.desc())
                .limit(limit)
            )
            return list(db.scalars(stmt).all())

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Perform any cleanup (currently a no-op; sessions auto-close)."""
        logger.info("MemoryManager closed.")
