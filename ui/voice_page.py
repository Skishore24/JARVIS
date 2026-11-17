"""
JARVIS Voice Page.
Large mic button, PTT, wake word toggle, audio level visualiser,
transcript display, voice settings.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QTextEdit, QVBoxLayout, QWidget,
)

from ui.widgets.waveform_widget import WaveformWidget


class VoicePage(QWidget):
    """Voice control interface."""

    mic_toggle = Signal(bool)          # True = start listening
    ptt_pressed = Signal()
    ptt_released = Signal()
    wake_word_toggle = Signal(bool)
    settings_changed = Signal(dict)    # keys: speed, volume, stt_model

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._listening = False
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # Title
        title = QLabel("🎙  Voice Control")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #00bcd4;"
        )
        root.addWidget(title)

        # Main row: big mic + right panel
        main_row = QHBoxLayout()
        main_row.setSpacing(24)

        # -- Big mic button area
        mic_frame = QFrame()
        mic_frame.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 16px; }"
        )
        mic_col = QVBoxLayout(mic_frame)
        mic_col.setContentsMargins(30, 30, 30, 30)
        mic_col.setSpacing(16)
        mic_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(120, 120)
        self._mic_btn.setStyleSheet(self._mic_btn_style(False))
        self._mic_btn.clicked.connect(self._toggle_listening)
        mic_col.addWidget(self._mic_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._mic_status_lbl = QLabel("Click to start listening")
        self._mic_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mic_status_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        mic_col.addWidget(self._mic_status_lbl)

        # PTT button
        self._ptt_btn = QPushButton("⏺  Hold to Talk")
        self._ptt_btn.setFixedHeight(44)
        self._ptt_btn.setStyleSheet(
            "QPushButton { background: #1e3a5f; border: 1px solid #2196f3;"
            " border-radius: 8px; color: #e2e8f0; font-size: 13px; }"
            "QPushButton:pressed { background: #22c55e; color: white; }"
        )
        self._ptt_btn.pressed.connect(self.ptt_pressed.emit)
        self._ptt_btn.released.connect(self.ptt_released.emit)
        mic_col.addWidget(self._ptt_btn)

        # Wake word toggle
        ww_row = QHBoxLayout()
        ww_lbl = QLabel("Wake Word:")
        ww_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self._ww_btn = QPushButton("OFF")
        self._ww_btn.setCheckable(True)
        self._ww_btn.setFixedHeight(30)
        self._ww_btn.setStyleSheet(self._toggle_style(False))
        self._ww_btn.toggled.connect(self._on_wake_word)
        ww_row.addWidget(ww_lbl)
        ww_row.addWidget(self._ww_btn)
        mic_col.addLayout(ww_row)

        # Waveform
        self._waveform = WaveformWidget()
        mic_col.addWidget(self._waveform)

        mic_frame.setMaximumWidth(280)
        main_row.addWidget(mic_frame)

        # -- Right panel: transcript + settings
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # Transcript
        trans_group = QGroupBox("Current Transcript")
        trans_group.setStyleSheet(self._group_style())
        trans_layout = QVBoxLayout(trans_group)
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setPlaceholderText("Transcribed speech will appear here…")
        self._transcript.setMinimumHeight(140)
        self._transcript.setStyleSheet(
            "QTextEdit { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 13px; padding: 8px; }"
        )
        trans_layout.addWidget(self._transcript)
        right_col.addWidget(trans_group)

        # Settings
        settings_group = QGroupBox("Voice Settings")
        settings_group.setStyleSheet(self._group_style())
        s_layout = QVBoxLayout(settings_group)
        s_layout.setSpacing(12)

        # Speech speed
        speed_row = QHBoxLayout()
        speed_lbl = QLabel("Speed:")
        speed_lbl.setFixedWidth(70)
        speed_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(50, 300)
        self._speed_slider.setValue(150)
        self._speed_slider.setStyleSheet(self._slider_style())
        self._speed_val = QLabel("150")
        self._speed_val.setFixedWidth(36)
        self._speed_val.setStyleSheet("color: #00bcd4; font-size: 12px;")
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_val.setText(str(v))
        )
        speed_row.addWidget(speed_lbl)
        speed_row.addWidget(self._speed_slider, 1)
        speed_row.addWidget(self._speed_val)
        s_layout.addLayout(speed_row)

        # Volume
        vol_row = QHBoxLayout()
        vol_lbl = QLabel("Volume:")
        vol_lbl.setFixedWidth(70)
        vol_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setStyleSheet(self._slider_style())
        self._vol_val = QLabel("80")
        self._vol_val.setFixedWidth(36)
        self._vol_val.setStyleSheet("color: #00bcd4; font-size: 12px;")
        self._vol_slider.valueChanged.connect(
            lambda v: self._vol_val.setText(str(v))
        )
        vol_row.addWidget(vol_lbl)
        vol_row.addWidget(self._vol_slider, 1)
        vol_row.addWidget(self._vol_val)
        s_layout.addLayout(vol_row)

        # STT model
        model_row = QHBoxLayout()
        model_lbl = QLabel("STT Model:")
        model_lbl.setFixedWidth(70)
        model_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self._stt_combo = QComboBox()
        self._stt_combo.addItems(["tiny", "base", "small", "medium"])
        self._stt_combo.setStyleSheet(self._combo_style())
        model_row.addWidget(model_lbl)
        model_row.addWidget(self._stt_combo, 1)
        s_layout.addLayout(model_row)

        # Apply button
        apply_btn = QPushButton("Apply Settings")
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(
            "QPushButton { background: #2196f3; border: none; border-radius: 8px;"
            " color: white; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #1976d2; }"
        )
        apply_btn.clicked.connect(self._on_apply_settings)
        s_layout.addWidget(apply_btn)

        right_col.addWidget(settings_group)
        right_col.addStretch()
        main_row.addLayout(right_col, 1)
        root.addLayout(main_row)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _mic_btn_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: radial-gradient(circle, #22c55e, #16a34a);"
                " border: 3px solid #22c55e; border-radius: 60px;"
                " font-size: 48px; color: white; }"
                "QPushButton:hover { background: #16a34a; }"
            )
        return (
            "QPushButton { background: #1e3a5f; border: 3px solid #2196f3;"
            " border-radius: 60px; font-size: 48px; }"
            "QPushButton:hover { background: #2d4a7f; border-color: #00bcd4; }"
        )

    @staticmethod
    def _toggle_style(active: bool) -> str:
        if active:
            return (
                "QPushButton { background: #22c55e; border: none; border-radius: 6px;"
                " color: white; font-size: 11px; font-weight: bold; padding: 0 10px; }"
            )
        return (
            "QPushButton { background: #1e3a5f; border: 1px solid #64748b;"
            " border-radius: 6px; color: #64748b; font-size: 11px; padding: 0 10px; }"
        )

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 12px; color: #64748b; font-size: 11px;"
            " font-weight: bold; padding-top: 18px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; top: 4px; }"
        )

    @staticmethod
    def _slider_style() -> str:
        return (
            "QSlider::groove:horizontal { height: 4px; background: #1e3a5f; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #00bcd4; border: none;"
            " width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }"
            "QSlider::sub-page:horizontal { background: #2196f3; border-radius: 2px; }"
        )

    @staticmethod
    def _combo_style() -> str:
        return (
            "QComboBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #111827; color: #e2e8f0;"
            " selection-background-color: #1e3a5f; border: 1px solid #1e3a5f; }"
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _toggle_listening(self) -> None:
        self._listening = not self._listening
        self._mic_btn.setStyleSheet(self._mic_btn_style(self._listening))
        self._waveform.set_active(self._listening)
        if self._listening:
            self._mic_status_lbl.setText("Listening… click to stop")
            self._mic_status_lbl.setStyleSheet("color: #22c55e; font-size: 12px;")
        else:
            self._mic_status_lbl.setText("Click to start listening")
            self._mic_status_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        self.mic_toggle.emit(self._listening)

    def _on_wake_word(self, checked: bool) -> None:
        self._ww_btn.setText("ON" if checked else "OFF")
        self._ww_btn.setStyleSheet(self._toggle_style(checked))
        self.wake_word_toggle.emit(checked)

    def _on_apply_settings(self) -> None:
        self.settings_changed.emit({
            "speed": self._speed_slider.value(),
            "volume": self._vol_slider.value(),
            "stt_model": self._stt_combo.currentText(),
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_transcript(self, text: str) -> None:
        self._transcript.setPlainText(text)

    def append_transcript(self, text: str) -> None:
        current = self._transcript.toPlainText()
        self._transcript.setPlainText(current + text)

    def set_listening(self, active: bool) -> None:
        if self._listening != active:
            self._toggle_listening()

    def set_audio_levels(self, levels: list[float]) -> None:
        self._waveform.set_levels(levels)
