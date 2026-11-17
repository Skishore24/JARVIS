"""
system_control.py - System-level controls for JARVIS
Volume, screenshots, system info, process list, lock PC, battery.
"""

import ctypes
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Volume control – pycaw preferred, ctypes WinAPI fallback
# ---------------------------------------------------------------------------

def _get_pycaw_volume_interface():
    """Return pycaw ISimpleAudioVolume interface or None."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)
    except Exception as e:
        logger.debug("pycaw not available: %s", e)
        return None


def _ctypes_set_volume(level: float) -> bool:
    """Set volume (0.0-1.0) using Windows API via ctypes (nircmd fallback)."""
    try:
        # WinAPI: waveOutSetVolume – sets wave volume (0 to 65535 per channel)
        volume_int = int(level * 65535)
        ctypes.windll.winmm.waveOutSetVolume(0, (volume_int | (volume_int << 16)))
        return True
    except Exception as e:
        logger.error("ctypes set volume failed: %s", e)
        return False


def _ctypes_get_volume() -> Optional[float]:
    """Get current volume as 0.0-1.0 using WinAPI."""
    try:
        vol = ctypes.c_uint()
        ctypes.windll.winmm.waveOutGetVolume(0, ctypes.byref(vol))
        # low word is left channel
        return (vol.value & 0xFFFF) / 65535.0
    except Exception as e:
        logger.error("ctypes get volume failed: %s", e)
        return None


def get_volume() -> dict:
    """
    Get current system volume (0–100).

    Returns:
        dict with success, volume (int 0-100), muted (bool).
    """
    # Try pycaw first
    vol_interface = _get_pycaw_volume_interface()
    if vol_interface is not None:
        try:
            level = vol_interface.GetMasterVolumeLevelScalar()
            muted = bool(vol_interface.GetMute())
            return {
                "success": True,
                "volume": round(level * 100),
                "muted": muted,
                "source": "pycaw",
            }
        except Exception as e:
            logger.warning("pycaw get volume failed: %s", e)

    # Fallback: ctypes
    level = _ctypes_get_volume()
    if level is not None:
        return {
            "success": True,
            "volume": round(level * 100),
            "muted": False,
            "source": "ctypes",
        }

    return {"success": False, "error": "Could not retrieve system volume"}


def set_volume(level: int) -> dict:
    """
    Set system volume.

    Args:
        level: 0–100 integer volume level.

    Returns:
        dict with success, volume, message or error.
    """
    level = max(0, min(100, int(level)))
    scalar = level / 100.0

    # Try pycaw
    vol_interface = _get_pycaw_volume_interface()
    if vol_interface is not None:
        try:
            vol_interface.SetMasterVolumeLevelScalar(scalar, None)
            return {"success": True, "volume": level, "message": f"Volume set to {level}%"}
        except Exception as e:
            logger.warning("pycaw set volume failed: %s", e)

    # Fallback: ctypes WinAPI
    if _ctypes_set_volume(scalar):
        return {"success": True, "volume": level, "message": f"Volume set to {level}% (ctypes)"}

    # Fallback: PowerShell
    try:
        ps_cmd = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"$obj.SendKeys([char]173);"  # mute toggle trick - not ideal but workable
        )
        # Actually use nircmd if available
        subprocess.run(["nircmd.exe", "setsysvolume", str(int(scalar * 65535))],
                       capture_output=True, check=True)
        return {"success": True, "volume": level, "message": f"Volume set to {level}% (nircmd)"}
    except Exception:
        pass

    return {"success": False, "error": "Could not set system volume (pycaw and ctypes both failed)"}


def mute_volume() -> dict:
    """Mute system audio."""
    vol_interface = _get_pycaw_volume_interface()
    if vol_interface is not None:
        try:
            vol_interface.SetMute(1, None)
            return {"success": True, "muted": True, "message": "Volume muted"}
        except Exception as e:
            logger.warning("pycaw mute failed: %s", e)

    # PowerShell fallback (toggle mute via keypress simulation)
    try:
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.SendKeys]::SendWait([char]173)"
        )
        # Check current state first
        result = get_volume()
        if result.get("muted"):
            return {"success": True, "muted": True, "message": "Already muted"}
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        return {"success": True, "muted": True, "message": "Mute toggled (PowerShell)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def unmute_volume() -> dict:
    """Unmute system audio."""
    vol_interface = _get_pycaw_volume_interface()
    if vol_interface is not None:
        try:
            vol_interface.SetMute(0, None)
            return {"success": True, "muted": False, "message": "Volume unmuted"}
        except Exception as e:
            logger.warning("pycaw unmute failed: %s", e)

    try:
        result = get_volume()
        if not result.get("muted", True):
            return {"success": True, "muted": False, "message": "Already unmuted"}
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.SendKeys]::SendWait([char]173)"
        )
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        return {"success": True, "muted": False, "message": "Unmuted (PowerShell)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

_SCREENSHOT_DIR = Path.home() / "Desktop" / "JARVIS_Screenshots"


def take_screenshot(filename: Optional[str] = None) -> dict:
    """
    Take a full-screen screenshot and save to Desktop/JARVIS_Screenshots.

    Args:
        filename: Optional base filename (without extension); timestamp used if None.

    Returns:
        dict with success, path, message or error.
    """
    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}"

    # Ensure no extension yet
    stem = Path(filename).stem
    save_path = _SCREENSHOT_DIR / f"{stem}.png"

    # Try PIL (Pillow)
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(str(save_path))
        return {"success": True, "path": str(save_path), "message": f"Screenshot saved: {save_path.name}"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning("PIL screenshot failed: %s", e)

    # Try mss
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Full screen
            img = sct.grab(monitor)
            from mss.tools import to_png
            to_png(img.rgb, img.size, output=str(save_path))
        return {"success": True, "path": str(save_path), "message": f"Screenshot saved: {save_path.name}"}
    except ImportError:
        pass
    except Exception as e:
        logger.warning("mss screenshot failed: %s", e)

    # Fallback: PowerShell
    try:
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            f"$bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, "
            f"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); "
            f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
            f"$g.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
            f"$bmp.Save('{str(save_path).replace(chr(92), chr(47))}');"
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, check=True)
        return {"success": True, "path": str(save_path), "message": f"Screenshot saved (PS): {save_path.name}"}
    except Exception as e:
        return {"success": False, "error": f"All screenshot methods failed: {e}"}


# ---------------------------------------------------------------------------
# Lock PC
# ---------------------------------------------------------------------------

def lock_pc() -> dict:
    """Lock the Windows workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "message": "Workstation locked"}
    except Exception as e:
        # Fallback
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            return {"success": True, "message": "Workstation locked (rundll32)"}
        except Exception as e2:
            return {"success": False, "error": f"Could not lock workstation: {e} / {e2}"}


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

def get_system_info() -> dict:
    """
    Get comprehensive system information.

    Returns:
        dict with cpu, ram, disk, battery, uptime, os info.
    """
    info: dict = {}

    # CPU
    try:
        info["cpu"] = {
            "percent": psutil.cpu_percent(interval=0.5),
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "frequency_mhz": round(psutil.cpu_freq().current, 1) if psutil.cpu_freq() else None,
        }
    except Exception as e:
        info["cpu"] = {"error": str(e)}

    # RAM
    try:
        vm = psutil.virtual_memory()
        info["ram"] = {
            "total_gb": round(vm.total / (1024 ** 3), 2),
            "used_gb": round(vm.used / (1024 ** 3), 2),
            "available_gb": round(vm.available / (1024 ** 3), 2),
            "percent": vm.percent,
        }
    except Exception as e:
        info["ram"] = {"error": str(e)}

    # Disk
    try:
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fs": partition.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
        info["disk"] = disks
    except Exception as e:
        info["disk"] = {"error": str(e)}

    # Battery
    info["battery"] = get_battery_info()

    # Uptime
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime = str(timedelta(seconds=int(uptime_seconds)))
        info["uptime"] = {
            "seconds": int(uptime_seconds),
            "formatted": uptime,
            "boot_time": datetime.fromtimestamp(boot_time).isoformat(),
        }
    except Exception as e:
        info["uptime"] = {"error": str(e)}

    # OS
    try:
        import platform
        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python": platform.python_version(),
        }
    except Exception as e:
        info["os"] = {"error": str(e)}

    info["success"] = True
    return info


def get_battery_info() -> dict:
    """
    Get battery percentage and charging status.

    Returns:
        dict with success, percent, plugged, time_left_seconds.
    """
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return {"success": True, "available": False, "message": "No battery detected (desktop PC)"}
        return {
            "success": True,
            "available": True,
            "percent": round(battery.percent, 1),
            "plugged": battery.power_plugged,
            "charging": battery.power_plugged and battery.percent < 100,
            "time_left_seconds": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
            "time_left_formatted": str(timedelta(seconds=battery.secsleft)) if battery.secsleft not in (
                psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN
            ) else "Unlimited / Unknown",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_running_processes(sort_by: str = "memory", limit: int = 20) -> dict:
    """
    Get a list of running processes.

    Args:
        sort_by: 'memory' | 'cpu' | 'name' | 'pid'
        limit:   Maximum processes to return.

    Returns:
        dict with success, processes (list), count.
    """
    _system_procs = {
        "system idle process", "system", "registry", "smss.exe",
        "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
        "fontdrvhost.exe",
    }

    processes: list[dict] = []
    for proc in psutil.process_iter(["name", "pid", "memory_info", "cpu_percent", "status", "username"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in _system_procs:
                continue
            mem = proc.info["memory_info"]
            processes.append({
                "name": proc.info["name"],
                "pid": proc.info["pid"],
                "memory_mb": round(mem.rss / (1024 * 1024), 1) if mem else 0,
                "cpu_percent": proc.info["cpu_percent"] or 0.0,
                "status": proc.info["status"],
                "username": proc.info.get("username", ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort
    sort_map = {
        "memory": lambda p: -p["memory_mb"],
        "cpu": lambda p: -p["cpu_percent"],
        "name": lambda p: p["name"].lower(),
        "pid": lambda p: p["pid"],
    }
    sort_fn = sort_map.get(sort_by, sort_map["memory"])
    processes.sort(key=sort_fn)

    return {
        "success": True,
        "processes": processes[:limit],
        "total_running": len(processes),
        "shown": min(limit, len(processes)),
    }


def kill_process(pid: int) -> dict:
    """
    Kill a process by PID.

    Args:
        pid: Process ID.

    Returns:
        dict with success, message or error.
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        return {"success": True, "killed": name, "pid": pid, "message": f"Killed {name} (PID {pid})"}
    except psutil.NoSuchProcess:
        return {"success": False, "error": f"No process with PID {pid}"}
    except psutil.AccessDenied:
        return {"success": False, "error": f"Access denied to kill PID {pid}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def shutdown_pc(delay_seconds: int = 0, restart: bool = False) -> dict:
    """
    Shutdown or restart the PC.

    Args:
        delay_seconds: Seconds to wait before action.
        restart:       If True, restart instead of shutdown.

    Returns:
        dict with success, message.
    """
    action = "/r" if restart else "/s"
    action_name = "Restart" if restart else "Shutdown"
    try:
        subprocess.Popen(
            ["shutdown.exe", action, "/t", str(delay_seconds), "/c", f"JARVIS initiated {action_name}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return {
            "success": True,
            "message": f"{action_name} scheduled in {delay_seconds} seconds",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancel_shutdown() -> dict:
    """Cancel a pending shutdown/restart."""
    try:
        subprocess.Popen(["shutdown.exe", "/a"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "message": "Scheduled shutdown cancelled"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SystemControlResult:
    """Wrapper result object for SystemControl methods."""
    def __init__(self, success: bool, message: str, data: dict | None = None) -> None:
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<SystemControlResult success={self.success} message='{self.message}'>"


class SystemControl:
    """Object-oriented interface for system and hardware control."""

    def get_volume(self) -> int:
        res = get_volume()
        return res.get("volume", 50) if isinstance(res, dict) else 50

    def set_volume(self, level: int) -> SystemControlResult:
        res = set_volume(level)
        msg = res.get("message") or res.get("error", "")
        return SystemControlResult(success=res.get("success", False), message=msg, data=res)

    def mute_volume(self) -> SystemControlResult:
        res = mute_volume()
        msg = res.get("message") or res.get("error", "")
        return SystemControlResult(success=res.get("success", False), message=msg, data=res)

    def unmute_volume(self) -> SystemControlResult:
        res = unmute_volume()
        msg = res.get("message") or res.get("error", "")
        return SystemControlResult(success=res.get("success", False), message=msg, data=res)

    def take_screenshot(self, save_path: str | None = None) -> SystemControlResult:
        res = take_screenshot(save_path)
        msg = res.get("message") or res.get("error", "")
        return SystemControlResult(success=res.get("success", False), message=msg, data=res)

    def lock_pc(self) -> SystemControlResult:
        res = lock_pc()
        msg = res.get("message") or res.get("error", "")
        return SystemControlResult(success=res.get("success", False), message=msg, data=res)

    def get_system_info(self) -> SystemControlResult:
        res = get_system_info()
        cpu_pct = res.get("cpu", {}).get("percent", 0) if isinstance(res.get("cpu"), dict) else 0
        ram_pct = res.get("ram", {}).get("percent", 0) if isinstance(res.get("ram"), dict) else 0
        msg = f"CPU: {cpu_pct}%, RAM: {ram_pct}%"
        return SystemControlResult(success=res.get("success", True), message=msg, data=res)

