"""
Sidebar navigation button widget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)


class SidebarButton(QWidget):
    """Custom sidebar navigation button with icon + label."""

    clicked = Signal()

    NORMAL_STYLE = (
        "SidebarButton { background: transparent; border: none; border-radius: 8px; }"
        "SidebarButton:hover { background: #1e3a5f; }"
    )
    ACTIVE_STYLE = (
        "SidebarButton { background: #1e3a5f; border-left: 3px solid #00bcd4;"
        " border-radius: 8px; }"
    )

    def __init__(
        self,
        icon: str,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active = False
        self._icon = icon
        self._label = label
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        self._icon_lbl = QLabel(self._icon)
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text_lbl = QLabel(self._label)
        self._text_lbl.setStyleSheet(
            "font-size: 13px; color: #e2e8f0; background: transparent; border: none;"
        )

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

        self.setStyleSheet(self.NORMAL_STYLE)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setStyleSheet(self.ACTIVE_STYLE if active else self.NORMAL_STYLE)
        color = "#00bcd4" if active else "#e2e8f0"
        self._text_lbl.setStyleSheet(
            f"font-size: 13px; color: {color}; background: transparent; border: none;"
            + (" font-weight: bold;" if active else "")
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def is_active(self) -> bool:
        return self._active
