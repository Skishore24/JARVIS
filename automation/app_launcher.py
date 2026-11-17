"""
app_launcher.py - Application launcher and manager for JARVIS
Supports launching, closing, and listing Windows applications.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers & Office Dirs
# ---------------------------------------------------------------------------
def _office_dirs() -> list[str]:
    """Return potential Office installation directories."""
    base_dirs = [
        r"C:\Program Files\Microsoft Office",
        r"C:\Program Files (x86)\Microsoft Office",
    ]
    dirs: list[str] = []
    for base in base_dirs:
        base_path = Path(base)
        if base_path.exists():
            for child in base_path.iterdir():
                if child.is_dir():
                    dirs.append(str(child))
    return dirs or base_dirs


# ---------------------------------------------------------------------------
# Known app registry – maps friendly name → executable or search hints
# ---------------------------------------------------------------------------
APP_REGISTRY: dict[str, dict] = {
    # --- Common apps ---
    "notepad": {
        "exe": "notepad.exe",
        "process": "notepad.exe",
    },
    "calculator": {
        "exe": "calc.exe",
        "process": "CalculatorApp.exe",
        "uwp": True,
    },
    "paint": {
        "exe": "mspaint.exe",
        "process": "mspaint.exe",
    },
    "file explorer": {
        "exe": "explorer.exe",
        "process": "explorer.exe",
    },
    "explorer": {
        "exe": "explorer.exe",
        "process": "explorer.exe",
    },
    "task manager": {
        "exe": "taskmgr.exe",
        "process": "Taskmgr.exe",
    },
    "wordpad": {
        "exe": "wordpad.exe",
        "process": "wordpad.exe",
    },
    "cmd": {
        "exe": "cmd.exe",
        "process": "cmd.exe",
    },
    "powershell": {
        "exe": "powershell.exe",
        "process": "powershell.exe",
    },
    # --- Browsers ---
    "chrome": {
        "search_names": ["chrome.exe", "Google Chrome"],
        "search_dirs": [
            r"C:\Program Files\Google\Chrome\Application",
            r"C:\Program Files (x86)\Google\Chrome\Application",
            str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application"),
        ],
        "process": "chrome.exe",
    },
    "firefox": {
        "search_names": ["firefox.exe"],
        "search_dirs": [
            r"C:\Program Files\Mozilla Firefox",
            r"C:\Program Files (x86)\Mozilla Firefox",
        ],
        "process": "firefox.exe",
    },
    "edge": {
        "search_names": ["msedge.exe"],
        "search_dirs": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application",
            r"C:\Program Files\Microsoft\Edge\Application",
        ],
        "process": "msedge.exe",
    },
    # --- Development tools ---
    "vs code": {
        "search_names": ["Code.exe"],
        "search_dirs": [
            str(Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code"),
            r"C:\Program Files\Microsoft VS Code",
        ],
        "process": "Code.exe",
    },
    "vscode": {
        "search_names": ["Code.exe"],
        "search_dirs": [
            str(Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code"),
            r"C:\Program Files\Microsoft VS Code",
        ],
        "process": "Code.exe",
    },
    "visual studio code": {
        "search_names": ["Code.exe"],
        "search_dirs": [
            str(Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code"),
            r"C:\Program Files\Microsoft VS Code",
        ],
        "process": "Code.exe",
    },
    # --- Microsoft Office ---
    "word": {
        "search_names": ["WINWORD.EXE"],
        "search_dirs": _office_dirs(),
        "process": "WINWORD.EXE",
    },
    "excel": {
        "search_names": ["EXCEL.EXE"],
        "search_dirs": _office_dirs(),
        "process": "EXCEL.EXE",
    },
    "powerpoint": {
        "search_names": ["POWERPNT.EXE"],
        "search_dirs": _office_dirs(),
        "process": "POWERPNT.EXE",
    },
    "outlook": {
        "search_names": ["OUTLOOK.EXE"],
        "search_dirs": _office_dirs(),
        "process": "OUTLOOK.EXE",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_in_dirs(search_names: list[str], search_dirs: list[str]) -> Optional[str]:
    """Search directories for an executable by name."""
    for directory in search_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        for name in search_names:
            candidate = dir_path / name
            if candidate.exists():
                return str(candidate)
            # recursive one level
            for sub in dir_path.iterdir():
                if sub.is_dir():
                    candidate2 = sub / name
                    if candidate2.exists():
                        return str(candidate2)
    return None


def _find_in_start_menu(app_name: str) -> Optional[str]:
    """Search Windows Start Menu shortcuts for an app."""
    start_menu_dirs = [
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    name_lower = app_name.lower()
    for start_dir in start_menu_dirs:
        if not start_dir.exists():
            continue
        for lnk in start_dir.rglob("*.lnk"):
            if name_lower in lnk.stem.lower():
                return str(lnk)
    return None


def _launch_exe(exe_path: str, args: list[str] | None = None) -> dict:
    """Launch an executable with subprocess.Popen."""
    try:
        cmd = [exe_path] + (args or [])
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logger.info("Launched %s (PID %s)", exe_path, proc.pid)
        return {"success": True, "pid": proc.pid, "message": f"Launched successfully (PID {proc.pid})"}
    except FileNotFoundError:
        return {"success": False, "error": f"Executable not found: {exe_path}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _launch_shortcut(lnk_path: str) -> dict:
    """Launch a .lnk shortcut via explorer."""
    try:
        subprocess.Popen(
            ["explorer.exe", lnk_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"success": True, "message": f"Launched via shortcut: {lnk_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _launch_uwp(app_name: str) -> dict:
    """Launch a UWP app using the shell: URI scheme."""
    uwp_map = {
        "calculator": "calculator:",
        "settings": "ms-settings:",
        "store": "ms-windows-store:",
        "calendar": "outlookcal:",
        "mail": "outlookmail:",
        "photos": "ms-photos:",
        "maps": "bingmaps:",
        "weather": "bingweather:",
    }
    uri = uwp_map.get(app_name.lower())
    if uri:
        try:
            subprocess.Popen(["explorer.exe", uri])
            return {"success": True, "message": f"Launched UWP app via {uri}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": f"No UWP URI for: {app_name}"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def launch_app(app_name: str, args: list[str] | None = None) -> dict:
    """
    Launch an application by its friendly name.

    Returns:
        dict with keys: success (bool), message or error (str), pid (int, optional)
    """
    name_lower = app_name.strip().lower()

    entry = APP_REGISTRY.get(name_lower)

    if entry:
        # Direct exe (Windows built-ins)
        if "exe" in entry and not entry.get("search_names"):
            return _launch_exe(entry["exe"], args)

        # UWP apps
        if entry.get("uwp"):
            result = _launch_uwp(name_lower)
            if result["success"]:
                return result
            # Fallback to shell
            if "exe" in entry:
                return _launch_exe(entry["exe"], args)
            return result

        # Search in known directories
        if "search_names" in entry and "search_dirs" in entry:
            exe_path = _find_in_dirs(entry["search_names"], entry["search_dirs"])
            if exe_path:
                return _launch_exe(exe_path, args)

    # Fallback 1: Try Start Menu shortcut
    lnk = _find_in_start_menu(app_name)
    if lnk:
        return _launch_shortcut(lnk)

    # Fallback 2: Try running as a command directly (apps on PATH)
    try:
        guess_exe = app_name.replace(" ", "") + ".exe"
        proc = subprocess.Popen(
            [guess_exe] + (args or []),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS,
        )
        return {"success": True, "pid": proc.pid, "message": f"Launched {guess_exe} (PID {proc.pid})"}
    except FileNotFoundError:
        pass

    # Fallback 3: Use explorer to open by name (sometimes works for uwp)
    try:
        subprocess.Popen(["explorer.exe", f"shell:appsFolder"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return {
        "success": False,
        "error": (
            f"Could not find application '{app_name}'. "
            "Make sure it is installed and check the app name."
        ),
    }


def close_app(app_name: str, force: bool = False) -> dict:
    """
    Close application(s) by process name or friendly name.

    Args:
        app_name: Friendly name (e.g. 'chrome') or process name (e.g. 'chrome.exe')
        force: If True, SIGKILL; otherwise graceful terminate.

    Returns:
        dict with success, message, closed_count
    """
    name_lower = app_name.strip().lower()

    # Resolve process name from registry
    process_names: list[str] = []
    if name_lower in APP_REGISTRY:
        pname = APP_REGISTRY[name_lower].get("process")
        if pname:
            process_names.append(pname.lower())
        for sn in APP_REGISTRY[name_lower].get("search_names", []):
            process_names.append(sn.lower())
    else:
        # Treat as literal process name
        process_names.append(name_lower if name_lower.endswith(".exe") else name_lower + ".exe")
        process_names.append(name_lower)

    closed: list[str] = []
    errors: list[str] = []

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"].lower() in process_names:
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                closed.append(f"{proc.info['name']} (PID {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            errors.append(str(e))

    if closed:
        return {
            "success": True,
            "closed_count": len(closed),
            "message": f"Closed: {', '.join(closed)}",
        }
    return {
        "success": False,
        "closed_count": 0,
        "error": f"No running process found for '{app_name}'." + (f" Errors: {errors}" if errors else ""),
    }


def list_running_apps(include_system: bool = False) -> dict:
    """
    List currently running applications (non-system by default).

    Returns:
        dict with success, apps (list of dicts with name, pid, memory_mb)
    """
    _system_procs = {
        "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
        "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "conhost.exe",
        "taskhostw.exe", "sihost.exe", "fontdrvhost.exe", "spoolsv.exe",
    }

    apps: list[dict] = []
    seen: set[str] = set()

    for proc in psutil.process_iter(["name", "pid", "memory_info", "status"]):
        try:
            name = proc.info["name"] or ""
            if not include_system and name.lower() in _system_procs:
                continue
            if name in seen:
                continue
            seen.add(name)
            mem_mb = round(proc.info["memory_info"].rss / (1024 * 1024), 1) if proc.info["memory_info"] else 0
            apps.append({
                "name": name,
                "pid": proc.info["pid"],
                "memory_mb": mem_mb,
                "status": proc.info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    apps.sort(key=lambda x: x["name"].lower())
    return {"success": True, "apps": apps, "count": len(apps)}


def is_app_running(app_name: str) -> bool:
    """Check if an application is currently running."""
    name_lower = app_name.strip().lower()
    process_names: set[str] = set()

    if name_lower in APP_REGISTRY:
        pname = APP_REGISTRY[name_lower].get("process")
        if pname:
            process_names.add(pname.lower())
        for sn in APP_REGISTRY[name_lower].get("search_names", []):
            process_names.add(sn.lower())
    else:
        process_names.add(name_lower)
        process_names.add(name_lower + ".exe")

    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"].lower() in process_names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def get_app_info(app_name: str) -> dict:
    """Get info about all running instances of an app."""
    name_lower = app_name.strip().lower()
    process_names: set[str] = set()

    if name_lower in APP_REGISTRY:
        pname = APP_REGISTRY[name_lower].get("process")
        if pname:
            process_names.add(pname.lower())
        for sn in APP_REGISTRY[name_lower].get("search_names", []):
            process_names.add(sn.lower())
    else:
        process_names.add(name_lower)
        process_names.add(name_lower + ".exe")

    instances: list[dict] = []
    for proc in psutil.process_iter(["name", "pid", "memory_info", "cpu_percent", "create_time"]):
        try:
            if proc.info["name"].lower() in process_names:
                mem = proc.info["memory_info"]
                instances.append({
                    "name": proc.info["name"],
                    "pid": proc.info["pid"],
                    "memory_mb": round(mem.rss / (1024 * 1024), 1) if mem else 0,
                    "cpu_percent": proc.info["cpu_percent"],
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "success": True,
        "app": app_name,
        "running": len(instances) > 0,
        "instances": instances,
    }


class AppLauncherResult:
    """Wrapper result object for AppLauncher methods."""
    def __init__(self, success: bool, message: str, data: dict | None = None) -> None:
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<AppLauncherResult success={self.success} message='{self.message}'>"


class AppLauncher:
    """Object-oriented interface for application management."""

    def launch(self, app_name: str, args: list[str] | None = None) -> AppLauncherResult:
        res = launch_app(app_name, args)
        msg = res.get("message") or res.get("error", "Failed to launch")
        return AppLauncherResult(success=res.get("success", False), message=msg, data=res)

    def close(self, app_name: str, force: bool = False) -> AppLauncherResult:
        res = close_app(app_name, force)
        msg = res.get("message") or res.get("error", "Failed to close")
        return AppLauncherResult(success=res.get("success", False), message=msg, data=res)

    def is_running(self, app_name: str) -> bool:
        return is_app_running(app_name)

    def list_running(self) -> list[dict]:
        return list_running_apps()

