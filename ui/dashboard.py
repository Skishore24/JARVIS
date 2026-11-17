"""
JARVIS Dashboard Page.
Central orb, waveform, system stats, quick actions, activity log, text input.
"""
from __future__ import annotations

import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ui.widgets.orb_widget import OrbWidget
from ui.widgets.stat_card import StatCard
from ui.widgets.waveform_widget import WaveformWidget


class DashboardPage(QWidget):
    """Main JARVIS dashboard."""

    # Signals emitted to business logic layer
    send_message = Signal(str)
    action_triggered = Signal(str)   # search / screenshot / sysinfo / openapp
    mic_toggle = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._start_clock()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Top row: orb + stats
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # -- Orb area
        orb_frame = QFrame()
        orb_frame.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #1e3a5f; border-radius: 14px; }"
        )
        orb_layout = QVBoxLayout(orb_frame)
        orb_layout.setContentsMargins(20, 20, 20, 20)
        orb_layout.setSpacing(10)

        self.orb = OrbWidget()
        self.orb.setMinimumSize(180, 180)
        orb_layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignCenter)

        self._state_lbl = QLabel("IDLE")
        self._state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_lbl.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #00bcd4;"
            " letter-spacing: 3px;"
        )
        orb_layout.addWidget(self._state_lbl)

        # Waveform
        self.waveform = WaveformWidget()
        orb_layout.addWidget(self.waveform)

        # Mic toggle
        mic_row = QHBoxLayout()
        self._mic_btn = QPushButton("🎙 Mic")
        self._mic_btn.setCheckable(True)
        self._mic_btn.setFixedHeight(32)
        self._mic_btn.setStyleSheet(self._mic_style(False))
        self._mic_btn.toggled.connect(self._on_mic_toggle)
        mic_row.addStretch()
        mic_row.addWidget(self._mic_btn)
        mic_row.addStretch()
        orb_layout.addLayout(mic_row)

        orb_frame.setMinimumWidth(240)
        orb_frame.setMaximumWidth(300)
        top_row.addWidget(orb_frame)

        # -- Right side: stats + quick actions + activity
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # Stats grid
        stats_group = QGroupBox("System Status")
        stats_group.setStyleSheet(self._group_style())
        stats_grid = QGridLayout(stats_group)
        stats_grid.setSpacing(10)

        self._cpu_card = StatCard("CPU", "🖥️", "0%")
        self._ram_card = StatCard("RAM", "💾", "0%")
        self._bat_card = StatCard("Battery", "🔋", "—%")
        self._time_card = StatCard("Time", "🕐", "—:—")

        stats_grid.addWidget(self._cpu_card, 0, 0)
        stats_grid.addWidget(self._ram_card, 0, 1)
        stats_grid.addWidget(self._bat_card, 0, 2)
        stats_grid.addWidget(self._time_card, 0, 3)
        right_col.addWidget(stats_group)

        # Quick actions
        qa_group = QGroupBox("Quick Actions")
        qa_group.setStyleSheet(self._group_style())
        qa_layout = QHBoxLayout(qa_group)
        qa_layout.setSpacing(10)

        actions = [
            ("🔍 Search", "search"),
            ("📸 Screenshot", "screenshot"),
            ("ℹ️ System Info", "sysinfo"),
            ("📂 Open App", "openapp"),
        ]
        for label, action_id in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._action_btn_style())
            btn.clicked.connect(lambda checked=False, aid=action_id: self.action_triggered.emit(aid))
            qa_layout.addWidget(btn)
        right_col.addWidget(qa_group)

        # Activity log
        act_group = QGroupBox("Recent Activity")
        act_group.setStyleSheet(self._group_style())
        act_layout = QVBoxLayout(act_group)
        self._activity_list = QListWidget()
        self._activity_list.setMaximumHeight(130)
        self._activity_list.setStyleSheet(
            "QListWidget { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; }"
            "QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #1e3a5f; }"
            "QListWidget::item:selected { background: #1e3a5f; }"
        )
        act_layout.addWidget(self._activity_list)
        right_col.addWidget(act_group)
        right_col.addStretch()

        top_row.addLayout(right_col, 1)
        root.addLayout(top_row)

        # -- Text input bar at bottom
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #1e3a5f; border-radius: 12px; }"
        )
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 8, 14, 8)
        input_layout.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask JARVIS anything…")
        self._input.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #e2e8f0;"
            " font-size: 14px; }"
        )
        self._input.returnPressed.connect(self._on_send)

        send_btn = QPushButton("Send ➤")
        send_btn.setFixedHeight(36)
        send_btn.setStyleSheet(
            "QPushButton { background: #2196f3; border: none; border-radius: 8px;"
            " color: white; font-size: 13px; padding: 0 18px; font-weight: bold; }"
            "QPushButton:hover { background: #1976d2; }"
            "QPushButton:pressed { background: #0d47a1; }"
        )
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(send_btn)
        root.addWidget(input_frame)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 12px; color: #64748b; font-size: 11px;"
            " font-weight: bold; padding-top: 18px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; top: 4px; }"
        )

    @staticmethod
    def _action_btn_style() -> str:
        return (
            "QPushButton { background: #1e3a5f; border: 1px solid #2196f3;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: #2196f3; color: white; }"
            "QPushButton:pressed { background: #1565c0; }"
        )

    @staticmethod
    def _mic_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: #22c55e; border: none; border-radius: 6px;"
                " color: white; font-size: 12px; padding: 0 14px; }"
                "QPushButton:hover { background: #16a34a; }"
            )
        return (
            "QPushButton { background: #1e3a5f; border: 1px solid #64748b;"
            " border-radius: 6px; color: #64748b; font-size: 12px; padding: 0 14px; }"
            "QPushButton:hover { background: #2d4a6f; }"
        )

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------
    def _start_clock(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self) -> None:
        now = datetime.datetime.now()
        self._time_card.set_value(now.strftime("%H:%M"))

    # ------------------------------------------------------------------
    # Slots / handlers
    # ------------------------------------------------------------------
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if text:
            self._input.clear()
            self.send_message.emit(text)
            self.add_activity(f"→ {text[:60]}")

    def _on_mic_toggle(self, checked: bool) -> None:
        self._mic_btn.setStyleSheet(self._mic_style(checked))
        self.mic_toggle.emit()
        self.waveform.set_active(checked)

    # ------------------------------------------------------------------
    # Public API (called by business logic)
    # ------------------------------------------------------------------
    def set_state(self, state: str) -> None:
        """Update JARVIS state display."""
        self._state_lbl.setText(state.upper())
        colors = {
            "IDLE": "#00bcd4",
            "LISTENING": "#22c55e",
            "THINKING": "#f59e0b",
            "SPEAKING": "#2196f3",
            "ERROR": "#ef4444",
        }
        color = colors.get(state.upper(), "#00bcd4")
        self._state_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {color};"
            " letter-spacing: 3px;"
        )
        self.orb.set_state(state)

    def set_cpu(self, pct: float) -> None:
        self._cpu_card.set_value(f"{pct:.0f}%")

    def set_ram(self, pct: float) -> None:
        self._ram_card.set_value(f"{pct:.0f}%")

    def set_battery(self, pct: float | None) -> None:
        self._bat_card.set_value(f"{pct:.0f}%" if pct is not None else "—")

    def add_activity(self, text: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M")
        item = QListWidgetItem(f"[{ts}] {text}")
        self._activity_list.insertItem(0, item)
        # Keep last 20
        while self._activity_list.count() > 20:
            self._activity_list.takeItem(self._activity_list.count() - 1)
