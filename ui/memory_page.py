"""
JARVIS Memory Page.
Allows users to view, search, create, and manage persistent memory notes and preferences.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QInputDialog,
)

from memory.memory_manager import MemoryManager


class MemoryPage(QWidget):
    """Persistent user memory and preferences management."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._memory = MemoryManager()
        self._setup_ui()
        self.refresh_memories()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("🧠  JARVIS Memory & Context")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00bcd4;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("➕ Add Note")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(self._btn_style("#00838f", "#00bcd4"))
        add_btn.clicked.connect(self._add_memory)
        header.addWidget(add_btn)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.setFixedHeight(34)
        del_btn.setStyleSheet(self._btn_style("#3b1e2a", "#ef4444"))
        del_btn.clicked.connect(self._delete_memory)
        header.addWidget(del_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(self._btn_style("#1e3a5f", "#2196f3"))
        refresh_btn.clicked.connect(self.refresh_memories)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Filter bar
        filter_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter memories and past conversation snippets...")
        self._search_input.setStyleSheet(
            "QLineEdit { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 13px; padding: 6px 12px; }"
            "QLineEdit:focus { border-color: #00bcd4; }"
        )
        self._search_input.textChanged.connect(self._filter_table)
        filter_row.addWidget(self._search_input)
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["ID / Role", "Timestamp", "Memory Content / Context"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(
            "QTableWidget { background: #111827; border: 1px solid #1e3a5f; border-radius: 10px;"
            " color: #e2e8f0; gridline-color: #1e3a5f; font-size: 13px; }"
            "QHeaderView::section { background: #0a0e1a; color: #00bcd4; border: 1px solid #1e3a5f; padding: 6px; font-weight: bold; }"
            "QTableWidget::item:selected { background: #1e3a5f; }"
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

    def refresh_memories(self) -> None:
        """Fetch and populate memory items."""
        try:
            from memory.database import get_session
            from memory.conversation import ConversationMessage
            from sqlalchemy import select

            with get_session() as db:
                stmt = select(ConversationMessage).order_by(ConversationMessage.timestamp.desc()).limit(100)
                msgs = list(db.scalars(stmt).all())

            self._table.setRowCount(len(msgs))
            for row, m in enumerate(msgs):
                role_item = QTableWidgetItem(f"[{m.role.upper()}] #{m.id}")
                time_str = m.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(m.timestamp, "strftime") else str(m.timestamp)
                time_item = QTableWidgetItem(time_str)
                content_item = QTableWidgetItem(m.content[:150] + ("..." if len(m.content) > 150 else ""))

                role_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self._table.setItem(row, 0, role_item)
                self._table.setItem(row, 1, time_item)
                self._table.setItem(row, 2, content_item)
        except Exception:
            pass

    def _filter_table(self, query: str) -> None:
        query = query.lower()
        for row in range(self._table.rowCount()):
            content_item = self._table.item(row, 2)
            match = True if not query else (content_item and query in content_item.text().lower())
            self._table.setRowHidden(row, not match)

    def _add_memory(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, "Add Custom Memory / Note", "Enter information or preference for JARVIS to remember:"
        )
        if ok and text.strip():
            session_id = self._memory.new_session(title="User Memory Note")
            self._memory.add_message(session_id, "user", f"[User Preference Note]: {text.strip()}")
            self.refresh_memories()

    def _delete_memory(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Selection", "Please select a row to delete.")
            return

        row = selected_rows[0].row()
        id_text = self._table.item(row, 0).text()
        # format: "[ROLE] #123"
        try:
            msg_id = int(id_text.split("#")[-1])
            from memory.database import get_session
            from memory.conversation import ConversationMessage
            from sqlalchemy import delete

            with get_session() as db:
                db.execute(delete(ConversationMessage).where(ConversationMessage.id == msg_id))
            self.refresh_memories()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete message: {e}")

    @staticmethod
    def _btn_style(bg: str, hover: str) -> str:
        return (
            f"QPushButton {{ background: {bg}; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; font-weight: 500; padding: 0 14px; }"
            f"QPushButton:hover {{ background: {hover}; color: white; border-color: {hover}; }}"
        )
