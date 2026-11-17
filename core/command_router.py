"""
core/command_router.py
----------------------
Routes AI-extracted intents to the correct tool handler.
Each registered handler receives a params dict and returns a string result.
"""

from __future__ import annotations

import logging
import subprocess
import webbrowser
from typing import Any, Callable

from core.permission_manager import PermissionManager
from services.system_monitor import SystemMonitor
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Type alias for a tool handler function
ToolHandler = Callable[[dict[str, Any]], str]


class CommandRouter:
    """
    Maps intent names → handler callables and dispatches tool calls.

    Handlers are plain functions (or bound methods) that accept a params dict
    and return a human-readable result string.
    """

    def __init__(
        self,
        permission_manager: PermissionManager,
        system_monitor: SystemMonitor,
        notification_service: NotificationService,
    ) -> None:
        self._pm = permission_manager
        self._monitor = system_monitor
        self._notifier = notification_service
        self._handlers: dict[str, ToolHandler] = {}

        self._register_default_handlers()
        logger.info("CommandRouter initialised with %d handlers.", len(self._handlers))

    # ── Handler Registration ──────────────────────────────────────────────────

    def register(self, intent: str, handler: ToolHandler) -> None:
        """Register a custom handler for an intent name."""
        self._handlers[intent.upper()] = handler
        logger.debug("Registered handler for intent '%s'.", intent)

    def _register_default_handlers(self) -> None:
        """Wire up all built-in tool handlers."""
        self._handlers = {
            "SYSTEM_MONITOR": self._handle_system_monitor,
            "OPEN_APP":        self._handle_open_app,
            "FILE_OPERATION":  self._handle_file_operation,
            "WEB_SEARCH":      self._handle_web_search,
            "NOTIFY":          self._handle_notify,
            "RUN_COMMAND":     self._handle_run_command,
            "CHAT":            self._handle_chat,
        }

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def dispatch(self, intent: str, params: dict[str, Any]) -> str:
        """
        Look up and execute the handler for *intent*.

        Returns:
            The handler's result string, or an error message.
        """
        key = intent.upper()

        if key not in self._handlers:
            msg = f"Unknown intent '{intent}'. I don't know how to handle that yet."
            logger.warning(msg)
            return msg

        try:
            self._pm.check_or_raise(key)
        except PermissionError as exc:
            return f"⛔ Permission denied: {exc}"

        try:
            result = self._handlers[key](params)
            logger.debug("Intent '%s' handled successfully.", key)
            return result
        except Exception as exc:
            logger.error("Handler for '%s' raised an error: %s", key, exc, exc_info=True)
            return f"❌ Error executing '{intent}': {exc}"

    # ── Built-in Handlers ─────────────────────────────────────────────────────

    def _handle_system_monitor(self, params: dict[str, Any]) -> str:
        metric = params.get("metric", "all").lower()

        if metric in ("cpu", "all"):
            stats = self._monitor.get_full_report()
            return self._monitor.format_report(stats)
        if metric == "ram":
            ram = self._monitor.get_memory()
            return (
                f"RAM: {ram['used_gb']:.1f} GB used / "
                f"{ram['total_gb']:.1f} GB total "
                f"({ram['percent']}% used)"
            )
        if metric == "battery":
            bat = self._monitor.get_battery()
            if bat:
                charge = f"{bat['percent']:.0f}%"
                status = "charging" if bat["charging"] else "on battery"
                return f"Battery: {charge} — {status}"
            return "No battery detected (desktop system)."
        if metric == "disk":
            disks = self._monitor.get_disk_usage()
            lines = []
            for d in disks:
                lines.append(
                    f"{d['device']}: {d['used_gb']:.1f}/{d['total_gb']:.1f} GB "
                    f"({d['percent']}% used)"
                )
            return "\n".join(lines) if lines else "No disk info available."

        # Fallback: full report
        stats = self._monitor.get_full_report()
        return self._monitor.format_report(stats)

    def _handle_open_app(self, params: dict[str, Any]) -> str:
        app = params.get("app", "").strip()
        if not app:
            return "Please specify which application to open."
        try:
            subprocess.Popen([app], shell=True)
            return f"✅ Launched '{app}'."
        except Exception as exc:
            return f"❌ Could not launch '{app}': {exc}"

    def _handle_file_operation(self, params: dict[str, Any]) -> str:
        import os
        import shutil
        from pathlib import Path

        logger.info("File operation received params: %s", params)

        # Look for operation in common keys or infer from presence of 'content'
        operation = (
            params.get("operation")
            or params.get("action")
            or params.get("type")
            or params.get("mode")
            or ("write" if "content" in params else "read")
        ).lower()
        path = params.get("path") or params.get("filename") or params.get("filepath") or ""
        dest = params.get("destination") or params.get("dest") or ""

        # Normalize placeholders and paths
        import re
        username = os.environ.get("USERNAME", "")
        userprofile = os.environ.get("USERPROFILE", f"C:\\Users\\{username}")
        path = re.sub(r'\[(user|username)\]', username, path, flags=re.IGNORECASE)
        path = re.sub(r'<(user|username)>', username, path, flags=re.IGNORECASE)
        path = path.replace("%USERNAME%", username).replace("%USERPROFILE%", userprofile)
        if path and (not os.path.isabs(path) or path.startswith("C:\\data") or path.startswith("data")):
            import config
            path = str(config.PROJECT_ROOT / path.replace("C:\\data", "data").lstrip("/\\"))

        if operation in ("read", "open", "view"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(4096)  # limit to 4 KB
                return f"📄 Contents of '{path}':\n{content}"
            except Exception as exc:
                return f"❌ Cannot read '{path}': {exc}"

        if operation in ("write", "create", "new", "touch"):
            content = params.get("content", "")
            try:
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"✅ File created: '{path}'."
            except Exception as exc:
                return f"❌ Cannot create '{path}': {exc}"

        if operation in ("delete", "remove"):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                return f"✅ Deleted '{path}'."
            except Exception as exc:
                return f"❌ Cannot delete '{path}': {exc}"

        if operation in ("list", "dir", "ls"):
            try:
                entries = os.listdir(path or ".")
                return "📁 " + "\n".join(entries)
            except Exception as exc:
                return f"❌ Cannot list '{path}': {exc}"

        if operation in ("copy", "cp"):
            try:
                shutil.copy2(path, dest)
                return f"✅ Copied '{path}' → '{dest}'."
            except Exception as exc:
                return f"❌ Cannot copy: {exc}"

        if operation in ("move", "mv"):
            try:
                shutil.move(path, dest)
                return f"✅ Moved '{path}' → '{dest}'."
            except Exception as exc:
                return f"❌ Cannot move: {exc}"

        return f"Unknown file operation '{operation}'."

    def _handle_web_search(self, params: dict[str, Any]) -> str:
        query = params.get("query", "").strip()
        if not query:
            return "Please provide a search query."
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return f"🔍 Opened search for: {query}"

    def _handle_notify(self, params: dict[str, Any]) -> str:
        title = params.get("title", "JARVIS")
        message = params.get("message", "")
        if not message:
            return "No notification message provided."
        success = self._notifier.send(title=title, message=message)
        return "🔔 Notification sent." if success else "⚠️ Could not send notification."

    def _handle_run_command(self, params: dict[str, Any]) -> str:
        cmd = params.get("command", "").strip()
        if not cmd:
            return "No command specified."
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr or "(no output)"
            return f"```\n{output[:2000]}\n```"
        except subprocess.TimeoutExpired:
            return "❌ Command timed out after 30 seconds."
        except Exception as exc:
            return f"❌ Command failed: {exc}"

    def _handle_chat(self, params: dict[str, Any]) -> str:
        # CHAT intent means the AI response itself is the reply; pass through.
        return params.get("response", "")
