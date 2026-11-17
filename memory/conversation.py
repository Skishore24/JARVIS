"""
memory/conversation.py
----------------------
SQLAlchemy ORM models for conversation sessions and messages.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memory.database import Base


class ConversationSession(Base):
    """
    Represents one continuous conversation session with JARVIS.
    A new session is created each time the assistant is started.
    """

    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Back-reference to messages
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.timestamp",
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id!r} created={self.created_at}>"


class ConversationMessage(Base):
    """
    A single turn in a conversation — either user, assistant, or system.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)   # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)   # captured tool intent
    tool_result: Mapped[str | None] = mapped_column(Text, nullable=True)    # tool execution result

    # Relationship back to session
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} session={self.session_id!r} "
            f"role={self.role!r} len={len(self.content)}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "intent": self.intent,
            "tool_result": self.tool_result,
        }
