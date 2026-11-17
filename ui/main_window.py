"""
JARVIS Main Window.
Futuristic desktop interface connecting Dashboard, Chat, Voice, Automation,
History, Memory, Settings, and About pages with background threading and system tray.
"""
from __future__ import annotations

import logging
import threading
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPixmap, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QSystemTrayIcon,
    QVBoxLayout, QWidget, QMenu,
)

import config
from core.assistant import Assistant
from services.system_monitor import SystemMonitor
from voice.audio_manager import AudioManager, AudioState
from voice.text_to_speech import TextToSpeech

from ui.dashboard import DashboardPage
from ui.chat_page import ChatPage
from ui.voice_page import VoicePage
from ui.automation_page import AutomationPage
from ui.history_page import HistoryPage
from ui.memory_page import MemoryPage
from ui.settings_page import SettingsPage
from ui.about_page import AboutPage
from ui.widgets.sidebar_button import SidebarButton

logger = logging.getLogger(__name__)


class AIWorkerThread(QThread):
    """Executes AI queries in background so the UI remains fluid."""
    chunk_received = Signal(str)
    response_complete = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, assistant: Assistant, prompt: str, parent=None):
        super().__init__(parent)
        self._assistant = assistant
        self._prompt = prompt

    def run(self):
        try:
            full_reply = ""
            for chunk in self._assistant.stream_chat(self._prompt):
                full_reply += chunk
                self.chunk_received.emit(chunk)
            self.response_complete.emit(full_reply)
        except Exception as e:
            logger.exception("AI Worker error: %s", e)
            self.error_occurred.emit(str(e))


class MainWindow(QMainWindow):
    """Master JARVIS Application Window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.ASSISTANT_NAME} — AI Desktop Assistant")
        self.setMinimumSize(1200, 780)
        self.resize(1320, 840)

        # 1. Initialize Subsystems
        self._assistant = Assistant()
        self._assistant.start()

        self._monitor = SystemMonitor(update_interval=2.0)
        self._monitor.start()

        try:
            self._audio = AudioManager(parent=self)
            self._tts = self._audio.tts
            self._tts.start()  # Keep TTS running for all vocal responses
        except Exception as e:
            logger.warning("Audio manager initialization note: %s", e)
            self._audio = None
            self._tts = TextToSpeech()
            self._tts.start()

        self._last_was_voice: bool = False
        self._setup_female_voice()

        self._active_worker: AIWorkerThread | None = None

        # 2. Setup User Interface
        self._setup_ui()
        self._setup_tray()
        self._apply_global_style()
        self._wire_signals()

        # 3. Start Periodic Timers
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_system_stats)
        self._stats_timer.start(2000)

        logger.info("MainWindow initialized successfully.")

    def _setup_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(
            "QFrame { background: #0c1222; border-right: 1px solid #1e3a5f; }"
        )
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 18, 14, 18)
        sb_layout.setSpacing(8)

        # Logo / Title
        brand_row = QHBoxLayout()
        logo_orb = QLabel("⚡")
        logo_orb.setStyleSheet("font-size: 20px; color: #00bcd4;")
        brand_name = QLabel(config.ASSISTANT_NAME)
        brand_name.setStyleSheet("font-size: 20px; font-weight: bold; color: #00bcd4; letter-spacing: 2px;")
        brand_row.addWidget(logo_orb)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()
        sb_layout.addLayout(brand_row)

        sub_lbl = QLabel("SYSTEM ONLINE")
        sub_lbl.setStyleSheet("font-size: 10px; color: #22c55e; font-weight: bold; margin-left: 28px; margin-bottom: 12px;")
        sb_layout.addWidget(sub_lbl)

        # Nav Buttons
        self._nav_buttons: list[SidebarButton] = []
        nav_items = [
            ("📊", "Dashboard", 0),
            ("💬", "Chat", 1),
            ("🎙️", "Voice Assistant", 2),
            ("⚡", "PC Automation", 3),
            ("📜", "Task History", 4),
            ("🧠", "Memory", 5),
            ("⚙️", "Settings", 6),
            ("ℹ️", "About", 7),
        ]

        for icon, label, idx in nav_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda i=idx: self._switch_page(i))
            self._nav_buttons.append(btn)
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Stop / Emergency Action
        self._stop_btn = QPushButton("🛑 EMERGENCY STOP")
        self._stop_btn.setFixedHeight(38)
        self._stop_btn.setStyleSheet(
            "QPushButton { background: #450a0a; border: 1px solid #dc2626; border-radius: 8px;"
            " color: #fca5a5; font-size: 11px; font-weight: bold; letter-spacing: 1px; }"
            "QPushButton:hover { background: #dc2626; color: white; }"
            "QPushButton:pressed { background: #991b1b; }"
        )
        self._stop_btn.clicked.connect(self._emergency_stop)
        sb_layout.addWidget(self._stop_btn)

        root_layout.addWidget(sidebar)

        # ── Main Content Area ─────────────────────────────────────────────────
        content_frame = QFrame()
        content_frame.setStyleSheet("QFrame { background: #0a0e1a; }")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Header Bar
        top_bar = QFrame()
        top_bar.setFixedHeight(54)
        top_bar.setStyleSheet("QFrame { background: #111827; border-bottom: 1px solid #1e3a5f; }")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(20, 0, 20, 0)

        self._page_title_lbl = QLabel("Dashboard")
        self._page_title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #e2e8f0;")
        tb_layout.addWidget(self._page_title_lbl)
        tb_layout.addStretch()

        # Status pills in header
        self._ai_pill = QLabel(f"🤖 {config.OLLAMA_DEFAULT_MODEL}")
        self._ai_pill.setStyleSheet(
            "background: #1e3a5f; color: #00bcd4; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;"
        )
        self._status_pill = QLabel("● IDLE")
        self._status_pill.setStyleSheet(
            "background: #132e27; color: #22c55e; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;"
        )

        tb_layout.addWidget(self._ai_pill)
        tb_layout.addSpacing(8)
        tb_layout.addWidget(self._status_pill)

        content_layout.addWidget(top_bar)

        # Stacked Pages
        self._stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.chat_page = ChatPage()
        self.voice_page = VoicePage()
        self.automation_page = AutomationPage()
        self.history_page = HistoryPage()
        self.memory_page = MemoryPage()
        self.settings_page = SettingsPage()
        self.about_page = AboutPage()

        self._stack.addWidget(self.dashboard_page)    # 0
        self._stack.addWidget(self.chat_page)         # 1
        self._stack.addWidget(self.voice_page)        # 2
        self._stack.addWidget(self.automation_page)   # 3
        self._stack.addWidget(self.history_page)      # 4
        self._stack.addWidget(self.memory_page)       # 5
        self._stack.addWidget(self.settings_page)     # 6
        self._stack.addWidget(self.about_page)        # 7

        content_layout.addWidget(self._stack, 1)
        root_layout.addWidget(content_frame, 1)

        # Initial active button
        self._switch_page(0)

    def _setup_tray(self) -> None:
        """Create System Tray Icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        # Simple programmatic tray icon
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(16, 16, 15)
        grad.setColorAt(0, QColor("#00bcd4"))
        grad.setColorAt(1, QColor("#0a0e1a"))
        painter.setBrush(grad)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        self._tray = QSystemTrayIcon(QIcon(pix), self)
        self._tray.setToolTip(f"{config.ASSISTANT_NAME} AI Desktop Assistant")

        tray_menu = QMenu()
        show_action = QAction("Open JARVIS", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def _setup_female_voice(self) -> None:
        """Find and activate a female Windows voice (e.g., Microsoft Zira Desktop)."""
        try:
            voices = self._tts.list_voices()
            for v in voices:
                name_l = v.get("name", "").lower()
                id_l = v.get("id", "").lower()
                gender_s = str(v.get("gender", "") or "").lower()
                if "zira" in name_l or "female" in gender_s or "zira" in id_l or "eva" in name_l:
                    self._tts.set_voice(voice_id=v.get("id"))
                    logger.info("Female voice selected: %s", v.get("name"))
                    return
            if len(voices) > 1:
                self._tts.set_voice(voice_index=1)
                logger.info("Secondary voice selected as fallback for female voice.")
        except Exception as e:
            logger.warning("Could not set female voice: %s", e)

    def _wire_signals(self) -> None:
        """Connect UI components to assistant and automation backends."""
        # Dashboard input
        self.dashboard_page.send_message.connect(lambda txt: self._handle_user_message(txt, is_voice=False))
        self.dashboard_page.action_triggered.connect(self._handle_quick_action)
        self.dashboard_page.mic_toggle.connect(self._toggle_voice_listening)

        # Chat page input
        self.chat_page.send_message.connect(lambda txt: self._handle_user_message(txt, is_voice=False))

        # Voice page controls
        self.voice_page.mic_toggle.connect(self._toggle_voice_listening)
        self.voice_page.ptt_pressed.connect(self._start_voice_listening)
        self.voice_page.ptt_released.connect(self._stop_voice_listening)
        self.voice_page.wake_word_toggle.connect(self._on_wake_word_toggled)
        self.voice_page.settings_changed.connect(self._on_voice_settings_changed)

        # Audio manager signals
        if self._audio and hasattr(self._audio, "signals"):
            self._audio.signals.transcription_ready.connect(self._on_voice_transcription)
            self._audio.signals.state_changed.connect(self._on_audio_state_changed)
            self._audio.signals.audio_level_changed.connect(self._on_audio_level_changed)

        # Automation page triggers
        self.automation_page.action_completed.connect(
            lambda msg: self.dashboard_page.add_activity(f"Action: {msg[:40]}")
        )

        # Settings page updates
        self.settings_page.settings_saved.connect(self._on_settings_saved)

    def _switch_page(self, idx: int) -> None:
        """Switch current view."""
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == idx)

        titles = [
            "Dashboard", "Chat", "Voice Control", "PC Automation",
            "Task & Session History", "Memory & Knowledge", "Settings", "About JARVIS"
        ]
        self._page_title_lbl.setText(titles[idx] if idx < len(titles) else "JARVIS")

        if idx == 4:
            self.history_page.refresh_history()
        elif idx == 5:
            self.memory_page.refresh_memories()

    @Slot(str, float)
    def _on_voice_transcription(self, text: str, confidence: float) -> None:
        """Handle recognized speech from microphone."""
        text = text.strip()
        if text:
            logger.info("Voice input transcribed (conf=%.2f): %s", confidence, text)
            self.voice_page.set_transcript(text)
            self._handle_user_message(text, is_voice=True)

    def _start_voice_listening(self) -> None:
        if self._audio:
            self._audio.start()
            self._set_state("LISTENING")
            self.dashboard_page.set_mic_active(True)
            self.voice_page.set_mic_active(True)

    def _stop_voice_listening(self) -> None:
        if self._audio:
            self._audio.stop()
            self._set_state("IDLE")
            self.dashboard_page.set_mic_active(False)
            self.voice_page.set_mic_active(False)

    @Slot(str)
    def _on_audio_state_changed(self, state_name: str) -> None:
        state_u = state_name.upper()
        self._set_state(state_u)
        is_listening = state_u == "LISTENING"
        self.dashboard_page.set_mic_active(is_listening)
        self.voice_page.set_mic_active(is_listening)

    def _on_wake_word_toggled(self, enabled: bool) -> None:
        if self._audio:
            self._audio.set_wake_word_enabled(enabled)

    @Slot(float)
    def _on_audio_level_changed(self, level: float) -> None:
        self.voice_page.set_audio_levels([level] * 5)

    def _on_voice_settings_changed(self, settings: dict) -> None:
        if "speed" in settings and self._tts:
            self._tts.set_rate(int(settings["speed"]))
        if "volume" in settings and self._tts:
            self._tts.set_volume(float(settings["volume"]) / 100.0)

    def _handle_user_message(self, text: str, is_voice: bool = False) -> None:
        """Send message to AI via background worker."""
        if not text.strip():
            return

        self._last_was_voice = is_voice

        # Visual state
        self._set_state("THINKING")
        origin_tag = "🎙️ Voice" if is_voice else "💬 User"
        self.dashboard_page.add_activity(f"{origin_tag}: {text[:45]}")
        self.chat_page.add_user_message(text)
        self.chat_page.begin_streaming_message()

        # Launch background AI worker
        self._active_worker = AIWorkerThread(self._assistant, text)
        self._active_worker.chunk_received.connect(self._on_ai_chunk)
        self._active_worker.response_complete.connect(self._on_ai_complete)
        self._active_worker.error_occurred.connect(self._on_ai_error)
        self._active_worker.start()

    def _on_ai_chunk(self, chunk: str) -> None:
        self.chat_page.append_stream_chunk(chunk)

    def _on_ai_complete(self, full_response: str) -> None:
        self.chat_page.finish_streaming_message()
        self.dashboard_page.add_activity(f"JARVIS: {full_response[:45]}")
        self._set_state("SPEAKING")

        # Vocalize response using female voice
        try:
            if self._last_was_voice:
                # User asked via voice -> speak full natural response
                speech_text = self._clean_for_speech(full_response)
                if speech_text:
                    logger.info("Vocalizing voice response via female voice (%d chars)", len(speech_text))
                    self._tts.speak(speech_text)
            else:
                # Text input -> speak concise summary/first sentence
                concise = self._clean_for_speech(full_response.split("\n")[0])[:140]
                if concise and not concise.startswith(("{", "<", "[")):
                    self._tts.speak(concise)
        except Exception as e:
            logger.warning("TTS speech error: %s", e)

        QTimer.singleShot(2500, lambda: self._set_state("IDLE"))

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Convert markdown, JSON, and technical formatting to fluent, natural spoken English."""
        import re
        # Omit code blocks
        t = re.sub(r'```[\s\S]*?```', '', text)
        # Strip JSON-like objects
        t = re.sub(r'\{[\s\S]*?\}', '', t)
        # Clean inline code
        t = re.sub(r'`([^`]+)`', r'\1', t)
        # Clean markdown links
        t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)
        # Remove raw brackets
        t = re.sub(r'\[[^\[\]]*\]', '', t)
        # Remove bold / italic / bullet points / headers / technical symbols
        t = re.sub(r'[*_~#>-]', ' ', t)
        # Normalize whitespace
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _on_ai_error(self, err: str) -> None:
        self.chat_page.finish_streaming_message()
        self.chat_page.add_ai_message(f"⚠️ Error: {err}")
        self.dashboard_page.add_activity(f"Error: {err[:40]}")
        self._set_state("ERROR")
        QTimer.singleShot(3000, lambda: self._set_state("IDLE"))

    def _handle_quick_action(self, action_id: str) -> None:
        """Dashboard quick buttons."""
        if action_id == "search":
            self._switch_page(3)  # Automation page
        elif action_id == "screenshot":
            from automation.system_control import SystemControl
            sc = SystemControl()
            res = sc.take_screenshot()
            self.dashboard_page.add_activity(res.message)
        elif action_id == "sysinfo":
            summary = self._monitor.get_summary_text()
            self.chat_page.add_ai_message(f"**System Diagnostic Report:**\n\n```\n{summary}\n```")
            self._switch_page(1)
        elif action_id == "openapp":
            self._switch_page(3)

    def _toggle_voice_listening(self) -> None:
        """Toggle microphone listening."""
        if self._audio:
            if self._audio.state == AudioState.LISTENING:
                self._audio.stop()
                self._set_state("IDLE")
                self.dashboard_page.set_mic_active(False)
                self.voice_page.set_mic_active(False)
            else:
                success = self._audio.start()
                if success:
                    self._set_state("LISTENING")
                    self.dashboard_page.set_mic_active(True)
                    self.voice_page.set_mic_active(True)
                else:
                    self._set_state("ERROR")
                    self.dashboard_page.set_mic_active(False)
                    self.voice_page.set_mic_active(False)
                    QTimer.singleShot(2500, lambda: self._set_state("IDLE"))
        else:
            self._set_state("LISTENING")
            QTimer.singleShot(2000, lambda: self._set_state("IDLE"))

    def _emergency_stop(self) -> None:
        """Halt all speech, active AI tasks, and pending actions."""
        try:
            self._tts.interrupt()
        except Exception:
            pass
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()
        self._set_state("IDLE")
        self.dashboard_page.add_activity("🛑 Emergency Stop Executed")

    def _set_state(self, state: str) -> None:
        """Update orb and status pill."""
        self.dashboard_page.set_state(state)
        colors = {
            "IDLE": ("#132e27", "#22c55e"),
            "LISTENING": ("#064e3b", "#34d399"),
            "THINKING": ("#451a03", "#f59e0b"),
            "SPEAKING": ("#1e3a5f", "#38bdf8"),
            "ERROR": ("#450a0a", "#f87171"),
        }
        bg, fg = colors.get(state.upper(), ("#111827", "#00bcd4"))
        self._status_pill.setText(f"● {state.upper()}")
        self._status_pill.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;"
        )

    def _refresh_system_stats(self) -> None:
        """Periodic GUI refresh for system stats."""
        stats = self._monitor.get_stats()
        self.dashboard_page.set_cpu(stats.cpu_percent)
        self.dashboard_page.set_ram(stats.ram_percent)
        self.dashboard_page.set_battery(stats.battery_percent)

    def _on_settings_saved(self, settings: dict) -> None:
        model = settings.get("model")
        if model:
            self._assistant.switch_model(model)
            self._ai_pill.setText(f"🤖 {model}")
        QMessageBox.information(self, "Settings", "JARVIS settings updated successfully.")

    def _apply_global_style(self) -> None:
        """Global futuristic dark styling."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0e1a;
            }
            QWidget {
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QScrollBar:vertical {
                border: none;
                background: #0a0e1a;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1e3a5f;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00bcd4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def closeEvent(self, event) -> None:
        """Clean shutdown."""
        self._monitor.stop()
        self._assistant.stop()
        try:
            self._tts.stop()
        except Exception:
            pass
        if self._audio:
            try:
                self._audio.shutdown()
            except Exception:
                pass
        event.accept()
