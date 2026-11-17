"""
JARVIS PC Automation Page.
Direct controls and tools for system automation, app launching, file actions, and media.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget, QMessageBox,
)

from automation.app_launcher import AppLauncher
from automation.system_control import SystemControl
from automation.browser_control import BrowserControl
from automation.file_manager import FileManager


class AutomationPage(QWidget):
    """Direct Windows PC Automation interface."""

    action_completed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._launcher = AppLauncher()
        self._sys = SystemControl()
        self._browser = BrowserControl()
        self._files = FileManager()
        self._setup_ui()

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        # Header
        title = QLabel("⚡  Windows PC Automation")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00bcd4;")
        layout.addWidget(title)

        # --- Quick App Launch Grid ---
        app_group = QGroupBox("Application Management")
        app_group.setStyleSheet(self._group_style())
        app_grid = QGridLayout(app_group)
        app_grid.setSpacing(10)

        apps = [
            ("💻 VS Code", "vscode"),
            ("🌐 Google Chrome", "chrome"),
            ("📝 Notepad", "notepad"),
            ("🧮 Calculator", "calculator"),
            ("📁 File Explorer", "explorer"),
            ("⚙️ Task Manager", "task manager"),
            ("🎨 Paint", "paint"),
            ("⬛ Terminal / CMD", "cmd"),
        ]

        row = 0
        col = 0
        for name, key in apps:
            btn = QPushButton(name)
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._btn_style("#1e3a5f", "#2196f3"))
            btn.clicked.connect(lambda ch=False, k=key: self._launch_app(k))
            app_grid.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

        layout.addWidget(app_group)

        # --- Custom App / Command Launcher ---
        custom_app_group = QGroupBox("Custom Application Launcher")
        custom_app_group.setStyleSheet(self._group_style())
        custom_layout = QHBoxLayout(custom_app_group)
        self._custom_app_input = QLineEdit()
        self._custom_app_input.setPlaceholderText("Enter executable or application name (e.g. spotify, discord, winword)...")
        self._custom_app_input.setStyleSheet(self._input_style())
        self._custom_app_input.returnPressed.connect(self._launch_custom_app)

        launch_btn = QPushButton("Launch Application")
        launch_btn.setFixedHeight(36)
        launch_btn.setStyleSheet(self._btn_style("#00838f", "#00bcd4"))
        launch_btn.clicked.connect(self._launch_custom_app)

        custom_layout.addWidget(self._custom_app_input, 1)
        custom_layout.addWidget(launch_btn)
        layout.addWidget(custom_app_group)

        # --- System & Audio Controls ---
        sys_group = QGroupBox("System & Hardware Controls")
        sys_group.setStyleSheet(self._group_style())
        sys_layout = QVBoxLayout(sys_group)

        # Volume slider row
        vol_row = QHBoxLayout()
        vol_label = QLabel("🔊 System Volume:")
        vol_label.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        curr_vol = self._sys.get_volume()
        self._vol_slider.setValue(curr_vol)
        self._vol_slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 6px; background: #1e3a5f; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: #00bcd4; border-radius: 3px; }"
            "QSlider::handle:horizontal { background: #e2e8f0; width: 14px; margin: -4px 0; border-radius: 7px; }"
        )
        self._vol_slider.valueChanged.connect(self._on_volume_change)

        self._vol_val_lbl = QLabel(f"{curr_vol}%")
        self._vol_val_lbl.setStyleSheet("color: #00bcd4; font-weight: bold; width: 40px;")

        mute_btn = QPushButton("🔇 Mute")
        mute_btn.setFixedHeight(30)
        mute_btn.setStyleSheet(self._btn_style("#1e3a5f", "#ef4444"))
        mute_btn.clicked.connect(self._mute_toggle)

        vol_row.addWidget(vol_label)
        vol_row.addWidget(self._vol_slider, 1)
        vol_row.addWidget(self._vol_val_lbl)
        vol_row.addWidget(mute_btn)
        sys_layout.addLayout(vol_row)

        # System Action Buttons
        sys_btns = QHBoxLayout()
        shot_btn = QPushButton("📸 Take Screenshot")
        shot_btn.setFixedHeight(36)
        shot_btn.setStyleSheet(self._btn_style("#1e3a5f", "#2196f3"))
        shot_btn.clicked.connect(self._take_screenshot)

        lock_btn = QPushButton("🔒 Lock Computer")
        lock_btn.setFixedHeight(36)
        lock_btn.setStyleSheet(self._btn_style("#3b1e2a", "#f43f5e"))
        lock_btn.clicked.connect(self._lock_pc)

        info_btn = QPushButton("ℹ️ Refresh System Info")
        info_btn.setFixedHeight(36)
        info_btn.setStyleSheet(self._btn_style("#1e3a5f", "#00bcd4"))
        info_btn.clicked.connect(self._get_sys_info)

        sys_btns.addWidget(shot_btn)
        sys_btns.addWidget(lock_btn)
        sys_btns.addWidget(info_btn)
        sys_layout.addLayout(sys_btns)

        layout.addWidget(sys_group)

        # --- Browser & Web Actions ---
        web_group = QGroupBox("Web & Search")
        web_group.setStyleSheet(self._group_style())
        web_layout = QHBoxLayout(web_group)

        self._web_input = QLineEdit()
        self._web_input.setPlaceholderText("Search Google or enter web URL...")
        self._web_input.setStyleSheet(self._input_style())
        self._web_input.returnPressed.connect(self._search_web)

        search_btn = QPushButton("🔍 Google Search")
        search_btn.setFixedHeight(36)
        search_btn.setStyleSheet(self._btn_style("#1e3a5f", "#2196f3"))
        search_btn.clicked.connect(self._search_web)

        yt_btn = QPushButton("📺 YouTube Search")
        yt_btn.setFixedHeight(36)
        yt_btn.setStyleSheet(self._btn_style("#3b1e2a", "#ef4444"))
        yt_btn.clicked.connect(self._search_youtube)

        web_layout.addWidget(self._web_input, 1)
        web_layout.addWidget(search_btn)
        web_layout.addWidget(yt_btn)

        layout.addWidget(web_group)

        # Result / status label
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #22c55e; font-size: 13px; font-weight: bold;")
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

    def _launch_app(self, key: str) -> None:
        res = self._launcher.launch(key)
        self._update_status(res.message, res.success)

    def _launch_custom_app(self) -> None:
        target = self._custom_app_input.text().strip()
        if target:
            res = self._launcher.launch(target)
            self._update_status(res.message, res.success)
            self._custom_app_input.clear()

    def _on_volume_change(self, val: int) -> None:
        self._vol_val_lbl.setText(f"{val}%")
        self._sys.set_volume(val)

    def _mute_toggle(self) -> None:
        res = self._sys.mute_volume()
        self._update_status(res.message, res.success)

    def _take_screenshot(self) -> None:
        res = self._sys.take_screenshot()
        self._update_status(res.message, res.success)

    def _lock_pc(self) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Lock",
            "Are you sure you want to lock the computer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._sys.lock_pc()
            self._update_status("PC locked.", True)

    def _get_sys_info(self) -> None:
        res = self._sys.get_system_info()
        self._update_status(res.message, res.success)

    def _search_web(self) -> None:
        q = self._web_input.text().strip()
        if q:
            if q.startswith("http://") or q.startswith("https://") or ("." in q and " " not in q):
                res = self._browser.open_url(q)
            else:
                res = self._browser.google_search(q)
            self._update_status(res.message, res.success)

    def _search_youtube(self) -> None:
        q = self._web_input.text().strip()
        if q:
            res = self._browser.youtube_search(q)
            self._update_status(res.message, res.success)

    def _update_status(self, msg: str, success: bool) -> None:
        color = "#22c55e" if success else "#ef4444"
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
        self._status_lbl.setText(f"[{'✓' if success else '✗'}] {msg}")
        self.action_completed.emit(msg)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 12px; color: #64748b; font-size: 11px;"
            " font-weight: bold; padding-top: 20px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 14px; top: 4px; }"
        )

    @staticmethod
    def _input_style() -> str:
        return (
            "QLineEdit { background: #0a0e1a; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 13px; padding: 8px 12px; }"
            "QLineEdit:focus { border-color: #00bcd4; }"
        )

    @staticmethod
    def _btn_style(bg: str, hover: str) -> str:
        return (
            f"QPushButton {{ background: {bg}; border: 1px solid #1e3a5f;"
            " border-radius: 8px; color: #e2e8f0; font-size: 12px; font-weight: 500; padding: 0 14px; }"
            f"QPushButton:hover {{ background: {hover}; color: white; border-color: {hover}; }}"
            "QPushButton:pressed { opacity: 0.8; }"
        )
