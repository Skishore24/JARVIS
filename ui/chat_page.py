"""
JARVIS Chat Page.
Displays conversation history with animated message bubbles and streaming support.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ui.widgets.message_bubble import MessageBubble


class ChatPage(QWidget):
    """Full chat interface with bubble messages and streaming."""

    send_message = Signal(str)
    clear_chat = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._streaming_bubble: MessageBubble | None = None
        self._stream_buffer = ""
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            "QFrame { background: #111827; border-bottom: 1px solid #1e3a5f; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("💬  JARVIS Chat")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00bcd4;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._clear_btn = QPushButton("Clear Chat")
        self._clear_btn.setFixedHeight(30)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #ef4444;"
            " border-radius: 6px; color: #ef4444; font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: #ef4444; color: white; }"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        h_layout.addWidget(self._clear_btn)
        root.addWidget(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: #0a0e1a; }"
            "QScrollBar:vertical { width: 6px; background: #111827; }"
            "QScrollBar::handle:vertical { background: #1e3a5f; border-radius: 3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        self._messages_widget = QWidget()
        self._messages_widget.setStyleSheet("background: #0a0e1a;")
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(10, 16, 10, 16)
        self._messages_layout.setSpacing(6)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_widget)
        root.addWidget(self._scroll, 1)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame { background: #111827; border-top: 1px solid #1e3a5f; }"
        )
        input_frame.setFixedHeight(64)
        in_layout = QHBoxLayout(input_frame)
        in_layout.setContentsMargins(16, 12, 16, 12)
        in_layout.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message…")
        self._input.setStyleSheet(
            "QLineEdit { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 20px; color: #e2e8f0; font-size: 13px;"
            " padding: 0 16px; }"
            "QLineEdit:focus { border-color: #2196f3; }"
        )
        self._input.setFixedHeight(40)
        self._input.returnPressed.connect(self._on_send)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(40, 40)
        send_btn.setStyleSheet(
            "QPushButton { background: #2196f3; border: none; border-radius: 20px;"
            " color: white; font-size: 16px; }"
            "QPushButton:hover { background: #1976d2; }"
            "QPushButton:pressed { background: #0d47a1; }"
        )
        send_btn.clicked.connect(self._on_send)

        in_layout.addWidget(self._input, 1)
        in_layout.addWidget(send_btn)
        root.addWidget(input_frame)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if text:
            self._input.clear()
            self.add_user_message(text)
            self.send_message.emit(text)

    def _on_clear(self) -> None:
        # Remove all message bubbles
        while self._messages_layout.count() > 1:  # keep stretch
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._streaming_bubble = None
        self.clear_chat.emit()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _insert_bubble(self, bubble: MessageBubble) -> None:
        # Insert before the stretch (last item)
        idx = self._messages_layout.count() - 1
        self._messages_layout.insertWidget(idx, bubble)
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_user_message(self, text: str) -> None:
        bubble = MessageBubble(text, is_user=True)
        self._insert_bubble(bubble)

    def add_ai_message(self, text: str) -> None:
        bubble = MessageBubble(text, is_user=False)
        self._insert_bubble(bubble)

    def begin_streaming_message(self) -> None:
        """Start a streaming AI response (empty bubble to be updated)."""
        self._stream_buffer = ""
        self._streaming_bubble = MessageBubble("▌", is_user=False)
        self._insert_bubble(self._streaming_bubble)

    def append_stream_chunk(self, chunk: str) -> None:
        """Append a chunk to the current streaming message."""
        if self._streaming_bubble is None:
            self.begin_streaming_message()
        self._stream_buffer += chunk
        self._streaming_bubble.update_text(self._stream_buffer + "▌")
        self._scroll_to_bottom()

    def finish_streaming_message(self) -> None:
        """Finalise the streaming message."""
        if self._streaming_bubble:
            self._streaming_bubble.update_text(self._stream_buffer)
            self._streaming_bubble = None
        self._stream_buffer = ""

    def add_message(self, text: str, is_user: bool) -> None:
        if is_user:
            self.add_user_message(text)
        else:
            self.add_ai_message(text)
