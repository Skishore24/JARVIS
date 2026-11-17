"""
core/permission_manager.py
--------------------------
Validates whether a requested tool/action is permitted
based on configuration flags and an optional allowlist/denylist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import config

logger = logging.getLogger(__name__)


# ── Permission Categories ──────────────────────────────────────────────────────

@dataclass
class PermissionSet:
    """Mirrors the boolean flags from config."""
    file_system: bool = field(default_factory=lambda: config.ALLOW_FILE_SYSTEM_ACCESS)
    process_execution: bool = field(default_factory=lambda: config.ALLOW_PROCESS_EXECUTION)
    network: bool = field(default_factory=lambda: config.ALLOW_NETWORK_ACCESS)
    system_settings: bool = field(default_factory=lambda: config.ALLOW_SYSTEM_SETTINGS)


# Map tool/intent names → required permission category
_TOOL_PERMISSION_MAP: dict[str, str] = {
    "FILE_OPERATION": "file_system",
    "OPEN_APP": "process_execution",
    "RUN_COMMAND": "process_execution",
    "WEB_SEARCH": "network",
    "SYSTEM_MONITOR": "network",   # may ping remote endpoints
    "NOTIFY": "process_execution",
    "SYSTEM_SETTINGS": "system_settings",
    "CHAT": "none",
}


class PermissionManager:
    """
    Central authority for checking whether JARVIS may perform a tool action.

    Usage:
        pm = PermissionManager()
        if pm.is_allowed("FILE_OPERATION"):
            # proceed
    """

    def __init__(self, permissions: PermissionSet | None = None) -> None:
        self._perms = permissions or PermissionSet()
        self._denied_tools: set[str] = set()   # runtime denylist
        self._allowed_tools: set[str] = set()  # runtime allowlist overrides
        logger.info(
            "PermissionManager ready — fs=%s proc=%s net=%s sys=%s",
            self._perms.file_system,
            self._perms.process_execution,
            self._perms.network,
            self._perms.system_settings,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def is_allowed(self, tool_name: str) -> bool:
        """
        Return True if *tool_name* is permitted under the current permission set.

        Checks (in order):
        1. Runtime denylist (always denied).
        2. Runtime allowlist override (always allowed).
        3. Category-level config flag.
        """
        tool = tool_name.upper()

        if tool in self._denied_tools:
            logger.warning("Tool '%s' is in the runtime denylist.", tool)
            return False

        if tool in self._allowed_tools:
            return True

        category = _TOOL_PERMISSION_MAP.get(tool)
        if category is None:
            # Unknown tool — deny by default and log
            logger.warning("Unknown tool '%s' — denied by default.", tool)
            return False

        if category == "none" or category is None:
            # Explicitly no permission required (e.g., CHAT)
            return True

        allowed: bool = getattr(self._perms, category, False)
        if not allowed:
            logger.warning(
                "Tool '%s' requires permission '%s' which is DISABLED.", tool, category
            )
        return allowed

    def deny(self, tool_name: str) -> None:
        """Add a tool to the runtime denylist."""
        self._denied_tools.add(tool_name.upper())
        logger.info("Tool '%s' added to denylist.", tool_name)

    def allow_override(self, tool_name: str) -> None:
        """Force-allow a tool regardless of category flags (use carefully)."""
        self._denied_tools.discard(tool_name.upper())
        self._allowed_tools.add(tool_name.upper())
        logger.info("Tool '%s' force-allowed via runtime override.", tool_name)

    allow = allow_override

    def reset_runtime_overrides(self) -> None:
        """Clear all runtime denylist and allowlist entries."""
        self._denied_tools.clear()
        self._allowed_tools.clear()

    def get_permission_summary(self) -> dict[str, bool]:
        """Return a human-readable summary of current permissions."""
        return {
            "file_system": self._perms.file_system,
            "process_execution": self._perms.process_execution,
            "network": self._perms.network,
            "system_settings": self._perms.system_settings,
        }

    def check_or_raise(self, tool_name: str) -> None:
        """
        Check permission for *tool_name* and raise PermissionError if denied.
        Convenience method for use in guards.
        """
        if not self.is_allowed(tool_name):
            raise PermissionError(
                f"Action '{tool_name}' is not permitted. "
                "Check your .env permission settings."
            )
