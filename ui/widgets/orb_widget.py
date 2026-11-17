"""
Animated JARVIS Orb Widget.
Draws a pulsing glowing circle using QPainter with layered radial gradients.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QSequentialAnimationGroup,
    Qt, QTimer,
)
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


class OrbWidget(QWidget):
    """Central animated JARVIS orb with pulsing glow effect."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)

        # Pulse scale (1.0 = normal)
        self._pulse_scale: float = 1.0
        # Rotation angle for outer ring
        self._rotation: float = 0.0
        # Glow alpha 0-255
        self._glow_alpha: int = 180

        # State colours
        self._state_color = QColor("#00bcd4")  # cyan default

        # Pulse animation
        self._anim_group = QSequentialAnimationGroup(self)
        pulse_out = QPropertyAnimation(self, b"pulse_scale", self)
        pulse_out.setDuration(1200)
        pulse_out.setStartValue(1.0)
        pulse_out.setEndValue(1.12)
        pulse_out.setEasingCurve(QEasingCurve.Type.InOutSine)

        pulse_in = QPropertyAnimation(self, b"pulse_scale", self)
        pulse_in.setDuration(1200)
        pulse_in.setStartValue(1.12)
        pulse_in.setEndValue(1.0)
        pulse_in.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._anim_group.addAnimation(pulse_out)
        self._anim_group.addAnimation(pulse_in)
        self._anim_group.setLoopCount(-1)
        self._anim_group.start()

        # Rotation timer
        self._rot_timer = QTimer(self)
        self._rot_timer.timeout.connect(self._tick_rotation)
        self._rot_timer.start(16)  # ~60 fps

    # ------------------------------------------------------------------
    # Qt Property: pulse_scale
    # ------------------------------------------------------------------
    def _get_pulse_scale(self) -> float:
        return self._pulse_scale

    def _set_pulse_scale(self, value: float) -> None:
        self._pulse_scale = value
        self.update()

    pulse_scale = Property(float, _get_pulse_scale, _set_pulse_scale)

    # ------------------------------------------------------------------
    # Rotation tick
    # ------------------------------------------------------------------
    def _tick_rotation(self) -> None:
        self._rotation = (self._rotation + 0.5) % 360.0
        self.update()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_state(self, state: str) -> None:
        """Change orb colour based on JARVIS state."""
        colours = {
            "IDLE": "#00bcd4",
            "LISTENING": "#22c55e",
            "THINKING": "#f59e0b",
            "SPEAKING": "#2196f3",
            "ERROR": "#ef4444",
        }
        self._state_color = QColor(colours.get(state.upper(), "#00bcd4"))
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_r = min(w, h) * 0.32

        # Outer glow ring (rotating dashed arcs)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._rotation)
        ring_r = base_r * self._pulse_scale * 1.35
        glow_color = QColor(self._state_color)
        glow_color.setAlpha(60)
        from PySide6.QtGui import QPen
        pen = QPen(glow_color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(
            int(-ring_r), int(-ring_r), int(ring_r * 2), int(ring_r * 2)
        )
        painter.restore()

        # Second ring (counter-rotating)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._rotation * 0.6)
        ring2_r = base_r * self._pulse_scale * 1.18
        glow2 = QColor(self._state_color)
        glow2.setAlpha(40)
        from PySide6.QtGui import QPen as _Pen
        pen2 = _Pen(glow2, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen2)
        painter.drawEllipse(
            int(-ring2_r), int(-ring2_r), int(ring2_r * 2), int(ring2_r * 2)
        )
        painter.restore()

        # Outer glow (radial gradient halo)
        orb_r = base_r * self._pulse_scale
        halo_grad = QRadialGradient(cx, cy, orb_r * 1.6)
        halo_color = QColor(self._state_color)
        halo_color.setAlpha(80)
        halo_grad.setColorAt(0.0, halo_color)
        halo_color2 = QColor(self._state_color)
        halo_color2.setAlpha(0)
        halo_grad.setColorAt(1.0, halo_color2)
        painter.setBrush(halo_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(cx - orb_r * 1.6), int(cy - orb_r * 1.6),
            int(orb_r * 3.2), int(orb_r * 3.2)
        )

        # Main orb body
        orb_grad = QRadialGradient(cx - orb_r * 0.3, cy - orb_r * 0.3, orb_r * 1.2)
        core_light = QColor(self._state_color).lighter(160)
        core_light.setAlpha(255)
        orb_grad.setColorAt(0.0, core_light)
        orb_grad.setColorAt(0.4, self._state_color)
        dark_core = QColor("#0a0e1a")
        orb_grad.setColorAt(1.0, dark_core)
        painter.setBrush(orb_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(cx - orb_r), int(cy - orb_r),
            int(orb_r * 2), int(orb_r * 2)
        )

        # Inner highlight
        hi_r = orb_r * 0.38
        hi_grad = QRadialGradient(cx - orb_r * 0.25, cy - orb_r * 0.3, hi_r)
        hi_color = QColor(255, 255, 255, 120)
        hi_grad.setColorAt(0.0, hi_color)
        hi_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(hi_grad)
        painter.drawEllipse(
            int(cx - orb_r * 0.25 - hi_r),
            int(cy - orb_r * 0.3 - hi_r),
            int(hi_r * 2), int(hi_r * 2)
        )

        painter.end()
