"""
Stat Card Widget - displays a system metric (CPU, RAM, etc.).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    """Compact card showing an icon, label, and value."""

    def __init__(
        self,
        label: str,
        icon: str = "📊",
        value: str = "—",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label_text = label
        self._icon = icon
        self._setup_ui(value)

    def _setup_ui(self, initial_value: str) -> None:
        self.setStyleSheet(
            "StatCard {"
            "  background: #111827;"
            "  border: 1px solid #1e3a5f;"
            "  border-radius: 10px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        icon_lbl = QLabel(self._icon)
        icon_lbl.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_lbl = QLabel(initial_value)
        self._value_lbl.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #00bcd4;"
            "border: none; background: transparent;"
        )
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_lbl = QLabel(self._label_text)
        name_lbl.setStyleSheet(
            "font-size: 11px; color: #64748b; border: none; background: transparent;"
        )
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_lbl)
        layout.addWidget(self._value_lbl)
        layout.addWidget(name_lbl)

    def set_value(self, value: str) -> None:
        self._value_lbl.setText(value)
