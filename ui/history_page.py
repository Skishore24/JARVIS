"""
JARVIS Task & Conversation History Page.
Displays execution history, logs, and session records with filtering.
"""
from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QMessageBox,
)

from memory.memory_manager import MemoryManager


class HistoryPage(QWidget):
    """Task and conversation session history."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._memory = MemoryManager()
        self._setup_ui()
        self.refresh_history()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("📜  Task & Session History")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00bcd4;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(self._btn_style("#1e3a5f", "#2196f3"))
        refresh_btn.clicked.connect(self.refresh_history)
        header.addWidget(refresh_btn)

        clear_btn = QPushButton("🗑️ Clear Sessions")
        clear_btn.setFixedHeight(34)
        clear_btn.setStyleSheet(self._btn_style("#3b1e2a", "#ef4444"))
        clear_btn.clicked.connect(self._clear_history)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Date & Time", "Session Title", "Model Used", "Messages"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(
            "QTableWidget { background: #111827; border: 1px solid #1e3a5f; border-radius: 10px;"
            " color: #e2e8f0; gridline-color: #1e3a5f; font-size: 13px; }"
            "QHeaderView::section { background: #0a0e1a; color: #00bcd4; border: 1px solid #1e3a5f; padding: 6px; font-weight: bold; }"
            "QTableWidget::item:selected { background: #1e3a5f; }"
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def refresh_history(self) -> None:
        """Fetch and populate history records."""
        try:
            sessions = self._memory.list_sessions(limit=50)
            self._table.setRowCount(len(sessions))

            for row, s in enumerate(sessions):
                dt_str = s.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(s.created_at, "strftime") else str(s.created_at)
                msg_count = len(s.messages) if hasattr(s, "messages") and s.messages else 0

                item_dt = QTableWidgetItem(dt_str)
                item_title = QTableWidgetItem(s.title or f"Session {s.id[:8]}")
                item_model = QTableWidgetItem(s.model_used or "llama3.2:3b")
                item_msgs = QTableWidgetItem(str(msg_count))

                item_dt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_model.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_msgs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self._table.setItem(row, 0, item_dt)
                self._table.setItem(row, 1, item_title)
                self._table.setItem(row, 2, item_model)
                self._table.setItem(row, 3, item_msgs)
        except Exception as e:
            pass

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Sessions",
            "Are you sure you want to delete all stored conversation sessions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from memory.database import get_session
                from memory.conversation import ConversationSession, ConversationMessage
                from sqlalchemy import delete
                with get_session() as db:
                    db.execute(delete(ConversationMessage))
                    db.execute(delete(ConversationSession))
                self.refresh_history()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not clear sessions: {e}")

    @staticmethod
    def _btn_style(bg: str, hover: str) -> str:
        return (
            f"QPushButton {{ background: {bg}; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; font-weight: 500; padding: 0 16px; }"
            f"QPushButton:hover {{ background: {hover}; color: white; border-color: {hover}; }}"
        )
