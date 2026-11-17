"""
JARVIS About Page.
Displays system specifications, architecture overview, and version information.
"""
from __future__ import annotations

import platform
import psutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

import config


class AboutPage(QWidget):
    """About JARVIS information page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # Title Card
        title_box = QFrame()
        title_box.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #1e3a5f; border-radius: 14px; padding: 16px; }"
        )
        t_layout = QVBoxLayout(title_box)

        name_lbl = QLabel(f"🤖  {config.ASSISTANT_NAME} AI Desktop Assistant")
        name_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #00bcd4;")
        desc_lbl = QLabel(
            "An autonomous personal AI assistant inspired by Iron Man's J.A.R.V.I.S.\n"
            "Engineered for local-first intelligence, full PC automation, voice conversation, and persistent memory."
        )
        desc_lbl.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.4;")
        desc_lbl.setWordWrap(True)

        ver_lbl = QLabel("Version: 1.0.0 | Release: Production Ready | Platform: Windows 10/11 x64")
        ver_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-weight: bold;")

        t_layout.addWidget(name_lbl)
        t_layout.addWidget(desc_lbl)
        t_layout.addWidget(ver_lbl)
        layout.addWidget(title_box)

        # Specifications Group
        specs_group = QGroupBox("Target Machine & Hardware Specifications")
        specs_group.setStyleSheet(self._group_style())
        specs_layout = QGridLayout(specs_group)
        specs_layout.setSpacing(12)

        ram = psutil.virtual_memory()
        total_ram = f"{ram.total / (1024**3):.1f} GB"
        cpu_cores = f"{psutil.cpu_count(logical=False)} Cores / {psutil.cpu_count(logical=True)} Threads"

        items = [
            ("Operating System", f"Windows {platform.version()} ({platform.architecture()[0]})"),
            ("Processor", f"{platform.processor()} ({cpu_cores})"),
            ("Physical RAM", f"{total_ram} Total Installed"),
            ("Graphics Target", "NVIDIA RTX 3050 (6GB VRAM) / CUDA Support"),
            ("AI Inference Engine", f"Ollama Local Server ({config.OLLAMA_HOST})"),
            ("Active Model", config.OLLAMA_DEFAULT_MODEL),
            ("Speech-to-Text", "faster-whisper (tiny / base / GPU-accelerated)"),
            ("Text-to-Speech", "pyttsx3 (Native Windows SAPI Offline Voice)"),
        ]

        for i, (k, v) in enumerate(items):
            k_lbl = QLabel(k)
            k_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold;")
            v_lbl = QLabel(v)
            v_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px;")
            specs_layout.addWidget(k_lbl, i, 0)
            specs_layout.addWidget(v_lbl, i, 1)

        layout.addWidget(specs_group)

        # Architecture Highlights
        arch_group = QGroupBox("Security & Architecture Principles")
        arch_group.setStyleSheet(self._group_style())
        arch_layout = QVBoxLayout(arch_group)

        arch_points = [
            "🔒 Sandboxed Automation: LLM never executes raw unapproved shell commands directly.",
            "🛡️ Security Boundary: Explicit confirmation required for system locks and destructive actions.",
            "💾 100% Local Intelligence: Operates completely offline with zero telemetry or paid cloud APIs.",
            "⚡ Multi-Threaded Execution: Speech, AI streaming, and monitoring never freeze the GUI.",
            "🧠 Persistent SQLite Memory: Automatic conversation logs with user-controlled memory deletion.",
        ]
        for p in arch_points:
            p_lbl = QLabel(p)
            p_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; padding: 2px 0;")
            arch_layout.addWidget(p_lbl)

        layout.addWidget(arch_group)
        layout.addStretch()

        scroll.setWidget(container)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    @staticmethod
    def _group_style() -> str:
        return (
            "QGroupBox { background: #111827; border: 1px solid #1e3a5f;"
            " border-radius: 12px; color: #64748b; font-size: 11px;"
            " font-weight: bold; padding-top: 20px; margin-top: 6px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 14px; top: 4px; }"
        )
