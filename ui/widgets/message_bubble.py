"""
Message Bubble Widget for chat display.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)


class MessageBubble(QWidget):
    """A single chat message bubble (user or AI)."""

    def __init__(
        self,
        text: str,
        is_user: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_user = is_user
        self._text = text
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(8)

        self._bubble = _BubbleLabel(self._text, self.is_user)

        if self.is_user:
            outer.addStretch()
            outer.addWidget(self._bubble)
        else:
            # Avatar label
            avatar = QLabel("J")
            avatar.setFixedSize(32, 32)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(
                "background: #00bcd4; border-radius: 16px;"
                "color: #0a0e1a; font-weight: bold; font-size: 14px;"
            )
            outer.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
            outer.addWidget(self._bubble)
            outer.addStretch()

    def update_text(self, text: str) -> None:
        """Update text (for streaming)."""
        self._text = text
        self._bubble.setText(text)

    def get_text(self) -> str:
        return self._text


class _BubbleLabel(QLabel):
    """Rounded bubble label."""

    USER_BG = "#1e3a5f"
    AI_BG = "#111827"
    USER_BORDER = "#2196f3"
    AI_BORDER = "#1e3a5f"

    def __init__(self, text: str, is_user: bool) -> None:
        super().__init__(text)
        self.is_user = is_user
        self.setWordWrap(True)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.setMaximumWidth(520)
        self.setMinimumWidth(60)

        bg = self.USER_BG if is_user else self.AI_BG
        border = self.USER_BORDER if is_user else self.AI_BORDER
        align = "right" if is_user else "left"
        self.setStyleSheet(
            f"background: {bg}; border: 1px solid {border};"
            f"border-radius: 12px; color: #e2e8f0; font-size: 13px;"
            f"padding: 10px 14px; text-align: {align};"
        )
