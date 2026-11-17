"""
JARVIS Settings Page.
Tabs: AI, Voice, Automation, Privacy, Appearance.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt


class SettingsPage(QWidget):
    """Settings interface with multiple tabs."""

    settings_saved = Signal(dict)
    clear_history = Signal()
    clear_memory = Signal()
    export_data = Signal()
    theme_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        from PySide6.QtWidgets import QFrame
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(
            "QFrame { background: #111827; border-bottom: 1px solid #1e3a5f; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)
        title = QLabel("⚙️  Settings")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #00bcd4;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        save_btn = QPushButton("Save All")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet(
            "QPushButton { background: #2196f3; border: none; border-radius: 6px;"
            " color: white; font-size: 13px; font-weight: bold; padding: 0 18px; }"
            "QPushButton:hover { background: #1976d2; }"
        )
        save_btn.clicked.connect(self._on_save)
        h_layout.addWidget(save_btn)
        root.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #0a0e1a; }"
            "QTabBar::tab { background: #111827; color: #64748b; padding: 10px 20px;"
            " border: none; border-bottom: 2px solid transparent; font-size: 13px; }"
            "QTabBar::tab:selected { color: #00bcd4; border-bottom: 2px solid #00bcd4;"
            " background: #0a0e1a; }"
            "QTabBar::tab:hover { color: #e2e8f0; }"
        )
        self._tabs.addTab(self._build_ai_tab(), "🤖  AI")
        self._tabs.addTab(self._build_voice_tab(), "🎙  Voice")
        self._tabs.addTab(self._build_automation_tab(), "⚡  Automation")
        self._tabs.addTab(self._build_privacy_tab(), "🔒  Privacy")
        self._tabs.addTab(self._build_appearance_tab(), "🎨  Appearance")
        root.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------
    def _scrollable(self, inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: #0a0e1a; }"
            "QScrollBar:vertical { width: 6px; background: #111827; }"
            "QScrollBar::handle:vertical { background: #1e3a5f; border-radius: 3px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        scroll.setWidget(inner)
        return scroll

    def _page_widget(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        w.setStyleSheet("background: #0a0e1a;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        return w, lay

    def _group(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        g = QGroupBox(title)
        g.setStyleSheet(
            "QGroupBox { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 12px; color: #64748b; font-size: 11px;"
            " font-weight: bold; padding-top: 18px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; top: 4px; }"
        )
        f = QFormLayout(g)
        f.setContentsMargins(16, 20, 16, 16)
        f.setSpacing(12)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return g, f

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        return l

    def _combo(self, items: list[str]) -> QComboBox:
        c = QComboBox()
        c.addItems(items)
        c.setStyleSheet(
            "QComboBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #111827; color: #e2e8f0;"
            " selection-background-color: #1e3a5f; border: 1px solid #1e3a5f; }"
        )
        return c

    def _lineedit(self, placeholder: str = "", text: str = "") -> QLineEdit:
        e = QLineEdit(text)
        e.setPlaceholderText(placeholder)
        e.setStyleSheet(
            "QLineEdit { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
            "QLineEdit:focus { border-color: #2196f3; }"
        )
        return e

    # -- AI Tab --
    def _build_ai_tab(self) -> QScrollArea:
        w, lay = self._page_widget()

        g, f = self._group("AI Model")
        self._model_combo = self._combo([
            "llama3.2:3b", "llama3.1:8b", "gemma4:12b", "phi3", "mistral"
        ])
        self._ollama_url = self._lineedit("http://localhost:11434", "http://localhost:11434")
        self._ctx_spin = QSpinBox()
        self._ctx_spin.setRange(512, 32768)
        self._ctx_spin.setValue(4096)
        self._ctx_spin.setStyleSheet(
            "QSpinBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
        )
        self._temp_spin = QDoubleSpinBox()
        self._temp_spin.setRange(0.0, 2.0)
        self._temp_spin.setSingleStep(0.05)
        self._temp_spin.setValue(0.7)
        self._temp_spin.setStyleSheet(
            "QDoubleSpinBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
        )
        f.addRow(self._lbl("Model:"), self._model_combo)
        f.addRow(self._lbl("Ollama URL:"), self._ollama_url)
        f.addRow(self._lbl("Context Length:"), self._ctx_spin)
        f.addRow(self._lbl("Temperature:"), self._temp_spin)
        lay.addWidget(g)
        lay.addStretch()
        return self._scrollable(w)

    # -- Voice Tab --
    def _build_voice_tab(self) -> QScrollArea:
        w, lay = self._page_widget()

        g, f = self._group("Voice & Audio")
        self._mic_combo = self._combo(["Default Microphone", "Built-in Mic", "USB Mic"])
        self._tts_voice_combo = self._combo([
            "Microsoft David Desktop",
            "Microsoft Zira Desktop",
            "Microsoft Mark Desktop",
        ])
        self._speech_rate_spin = QSpinBox()
        self._speech_rate_spin.setRange(50, 400)
        self._speech_rate_spin.setValue(150)
        self._speech_rate_spin.setStyleSheet(
            "QSpinBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
        )
        self._tts_vol_spin = QSpinBox()
        self._tts_vol_spin.setRange(0, 100)
        self._tts_vol_spin.setValue(80)
        self._tts_vol_spin.setStyleSheet(
            "QSpinBox { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; }"
        )
        f.addRow(self._lbl("Microphone:"), self._mic_combo)
        f.addRow(self._lbl("TTS Voice:"), self._tts_voice_combo)
        f.addRow(self._lbl("Speech Rate:"), self._speech_rate_spin)
        f.addRow(self._lbl("TTS Volume:"), self._tts_vol_spin)
        lay.addWidget(g)
        lay.addStretch()
        return self._scrollable(w)

    # -- Automation Tab --
    def _build_automation_tab(self) -> QScrollArea:
        w, lay = self._page_widget()

        g_folders, f_folders = self._group("Allowed Folders")
        self._folders_list = QListWidget()
        self._folders_list.setMaximumHeight(130)
        self._folders_list.setStyleSheet(
            "QListWidget { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background: #1e3a5f; }"
        )
        self._folders_list.addItems([
            "C:\\Users\\Public\\Documents",
            "C:\\MyFiles\\Project\\JARVIS",
        ])

        folder_btns = QHBoxLayout()
        add_folder_btn = QPushButton("+ Add")
        add_folder_btn.setFixedHeight(30)
        add_folder_btn.setStyleSheet(self._small_btn_style("#22c55e"))
        add_folder_btn.clicked.connect(self._add_folder)

        rem_folder_btn = QPushButton("— Remove")
        rem_folder_btn.setFixedHeight(30)
        rem_folder_btn.setStyleSheet(self._small_btn_style("#ef4444"))
        rem_folder_btn.clicked.connect(self._remove_folder)

        folder_btns.addWidget(add_folder_btn)
        folder_btns.addWidget(rem_folder_btn)
        folder_btns.addStretch()

        from PySide6.QtWidgets import QVBoxLayout as _VL
        folders_inner = _VL()
        folders_inner.addWidget(self._folders_list)
        folders_inner.addLayout(folder_btns)
        container = QWidget()
        container.setLayout(folders_inner)
        f_folders.addRow(container)
        lay.addWidget(g_folders)

        g_perm, f_perm = self._group("Permissions")
        perms = [
            ("Allow file read/write", True),
            ("Allow app launch", True),
            ("Allow browser control", False),
            ("Allow system commands", False),
            ("Allow internet access", True),
        ]
        self._perm_checks: dict[str, QCheckBox] = {}
        for perm_name, default in perms:
            cb = QCheckBox()
            cb.setChecked(default)
            cb.setStyleSheet(
                "QCheckBox { color: #e2e8f0; font-size: 12px; }"
                "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #1e3a5f;"
                " border-radius: 3px; background: #0a0e1a; }"
                "QCheckBox::indicator:checked { background: #22c55e; border-color: #22c55e; }"
            )
            f_perm.addRow(self._lbl(perm_name), cb)
            self._perm_checks[perm_name] = cb
        lay.addWidget(g_perm)
        lay.addStretch()
        return self._scrollable(w)

    # -- Privacy Tab --
    def _build_privacy_tab(self) -> QScrollArea:
        w, lay = self._page_widget()

        g, f = self._group("Data Management")

        clear_hist_btn = QPushButton("🗑  Clear Conversation History")
        clear_hist_btn.setFixedHeight(38)
        clear_hist_btn.setStyleSheet(self._danger_btn_style())
        clear_hist_btn.clicked.connect(self._on_clear_history)

        clear_mem_btn = QPushButton("🧹  Clear All Memory")
        clear_mem_btn.setFixedHeight(38)
        clear_mem_btn.setStyleSheet(self._danger_btn_style())
        clear_mem_btn.clicked.connect(self._on_clear_memory)

        export_btn = QPushButton("📤  Export Data")
        export_btn.setFixedHeight(38)
        export_btn.setStyleSheet(
            "QPushButton { background: #2196f3; border: none; border-radius: 8px;"
            " color: white; font-size: 13px; padding: 0 18px; }"
            "QPushButton:hover { background: #1976d2; }"
        )
        export_btn.clicked.connect(self.export_data.emit)

        f.addRow(clear_hist_btn)
        f.addRow(clear_mem_btn)
        f.addRow(export_btn)
        lay.addWidget(g)
        lay.addStretch()
        return self._scrollable(w)

    # -- Appearance Tab --
    def _build_appearance_tab(self) -> QScrollArea:
        w, lay = self._page_widget()

        g, f = self._group("Appearance")
        self._theme_combo = self._combo([
            "JARVIS Dark (Navy)",
            "Midnight Black",
            "Cyber Purple",
            "Matrix Green",
        ])
        self._theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        f.addRow(self._lbl("Theme:"), self._theme_combo)
        lay.addWidget(g)
        lay.addStretch()
        return self._scrollable(w)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _small_btn_style(color: str) -> str:
        return (
            f"QPushButton {{ background: transparent; border: 1px solid {color};"
            f" border-radius: 6px; color: {color}; font-size: 11px; padding: 0 10px; }}"
            f"QPushButton:hover {{ background: {color}; color: white; }}"
        )

    @staticmethod
    def _danger_btn_style() -> str:
        return (
            "QPushButton { background: transparent; border: 1px solid #ef4444;"
            " border-radius: 8px; color: #ef4444; font-size: 13px; padding: 0 18px; }"
            "QPushButton:hover { background: #ef4444; color: white; }"
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._folders_list.addItem(folder)

    def _remove_folder(self) -> None:
        for item in self._folders_list.selectedItems():
            self._folders_list.takeItem(self._folders_list.row(item))

    def _on_clear_history(self) -> None:
        reply = QMessageBox.question(
            self, "Clear History",
            "Delete all conversation history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_history.emit()

    def _on_clear_memory(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Memory",
            "Delete all stored memories? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_memory.emit()

    def _on_save(self) -> None:
        settings = {
            "ai": {
                "model": self._model_combo.currentText(),
                "ollama_url": self._ollama_url.text(),
                "context_length": self._ctx_spin.value(),
                "temperature": self._temp_spin.value(),
            },
            "voice": {
                "mic": self._mic_combo.currentText(),
                "tts_voice": self._tts_voice_combo.currentText(),
                "speech_rate": self._speech_rate_spin.value(),
                "tts_volume": self._tts_vol_spin.value(),
            },
            "permissions": {
                name: cb.isChecked()
                for name, cb in self._perm_checks.items()
            },
            "theme": self._theme_combo.currentText(),
        }
        self.settings_saved.emit(settings)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_settings(self, settings: dict) -> None:
        """Populate controls from a settings dict."""
        ai = settings.get("ai", {})
        if "model" in ai:
            idx = self._model_combo.findText(ai["model"])
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
        if "ollama_url" in ai:
            self._ollama_url.setText(ai["ollama_url"])
        if "context_length" in ai:
            self._ctx_spin.setValue(ai["context_length"])
        if "temperature" in ai:
            self._temp_spin.setValue(ai["temperature"])
