"""
Audio Waveform Widget.
Displays animated bars that simulate audio level visualisation.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class WaveformWidget(QWidget):
    """Animated equaliser-style bar waveform."""

    BAR_COUNT = 24
    BAR_GAP = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(60)

        self._levels: list[float] = [0.05] * self.BAR_COUNT
        self._targets: list[float] = [0.05] * self.BAR_COUNT
        self._active = False
        self._accent = QColor("#00bcd4")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_active(self, active: bool) -> None:
        self._active = active

    def set_levels(self, levels: list[float]) -> None:
        """Accept normalised 0-1 audio levels (up to BAR_COUNT values)."""
        for i, v in enumerate(levels[: self.BAR_COUNT]):
            self._targets[i] = max(0.03, min(1.0, v))

    def set_accent_color(self, color: str) -> None:
        self._accent = QColor(color)

    # ------------------------------------------------------------------
    # Animation tick
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        changed = False
        for i in range(self.BAR_COUNT):
            if self._active:
                # Drift targets randomly to simulate audio
                self._targets[i] += random.uniform(-0.15, 0.15)
                self._targets[i] = max(0.05, min(1.0, self._targets[i]))
            else:
                self._targets[i] = 0.05

            # Smooth interpolation
            diff = self._targets[i] - self._levels[i]
            if abs(diff) > 0.005:
                self._levels[i] += diff * 0.3
                changed = True

        if changed:
            self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        total_gap = self.BAR_GAP * (self.BAR_COUNT - 1)
        bar_w = max(2, (w - total_gap) / self.BAR_COUNT)

        for i, level in enumerate(self._levels):
            x = i * (bar_w + self.BAR_GAP)
            bar_h = max(4, level * (h - 4))
            y = (h - bar_h) / 2

            grad = QLinearGradient(0, y, 0, y + bar_h)
            top_color = QColor(self._accent)
            top_color.setAlpha(230)
            bot_color = QColor(self._accent)
            bot_color.setAlpha(100)
            grad.setColorAt(0.0, top_color)
            grad.setColorAt(1.0, bot_color)

            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 2, 2)

        painter.end()
