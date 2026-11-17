"""
screenshot.py - Screen and window capture tools for JARVIS
Captures full screen or specific windows, saves with timestamp.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default save directory
# ---------------------------------------------------------------------------
DEFAULT_SAVE_DIR = Path.home() / "Desktop" / "JARVIS_Screenshots"


def _ensure_save_dir(directory: Path) -> Path:
    """Create the save directory if it doesn't exist."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _timestamped_name(prefix: str = "screenshot") -> str:
    """Generate a filename with current timestamp."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms precision
    return f"{prefix}_{ts}.png"


# ---------------------------------------------------------------------------
# Full-screen capture
# ---------------------------------------------------------------------------

def capture_screen(
    filename: Optional[str] = None,
    save_dir: Optional[str] = None,
    monitor: int = 0,
) -> dict:
    """
    Capture the entire screen (or a specific monitor).

    Args:
        filename:  Output filename (without extension). Timestamped if None.
        save_dir:  Directory to save to. Defaults to Desktop/JARVIS_Screenshots.
        monitor:   Monitor index (0 = all/primary for PIL; 1-based for mss).

    Returns:
        dict with success, path, width, height, message or error.
    """
    save_path_dir = _ensure_save_dir(Path(save_dir) if save_dir else DEFAULT_SAVE_DIR)
    fname = (filename or "screenshot") + ".png" if filename else _timestamped_name()
    save_path = save_path_dir / fname

    # --- Method 1: PIL ImageGrab ---
    try:
        from PIL import ImageGrab, Image
        img: Image.Image = ImageGrab.grab(all_screens=(monitor == 0))
        img.save(str(save_path), "PNG")
        w, h = img.size
        logger.info("Screenshot saved via PIL: %s (%dx%d)", save_path, w, h)
        return {
            "success": True,
            "path": str(save_path),
            "width": w,
            "height": h,
            "method": "PIL",
            "message": f"Screenshot saved: {save_path.name}",
        }
    except ImportError:
        logger.debug("PIL not available, trying mss")
    except Exception as e:
        logger.warning("PIL screenshot failed: %s", e)

    # --- Method 2: mss ---
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            mon_index = monitor if monitor > 0 else 0  # 0 = all, 1+ = specific
            mon = sct.monitors[mon_index]
            img_data = sct.grab(mon)
            mss.tools.to_png(img_data.rgb, img_data.size, output=str(save_path))
        logger.info("Screenshot saved via mss: %s", save_path)
        return {
            "success": True,
            "path": str(save_path),
            "width": img_data.size.width,
            "height": img_data.size.height,
            "method": "mss",
            "message": f"Screenshot saved: {save_path.name}",
        }
    except ImportError:
        logger.debug("mss not available, trying PowerShell")
    except Exception as e:
        logger.warning("mss screenshot failed: %s", e)

    # --- Method 3: pyautogui ---
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.save(str(save_path))
        w, h = img.size
        return {
            "success": True,
            "path": str(save_path),
            "width": w,
            "height": h,
            "method": "pyautogui",
            "message": f"Screenshot saved: {save_path.name}",
        }
    except ImportError:
        logger.debug("pyautogui not available, trying PowerShell")
    except Exception as e:
        logger.warning("pyautogui screenshot failed: %s", e)

    # --- Method 4: PowerShell GDI+ fallback ---
    try:
        ps_safe_path = str(save_path).replace("\\", "/")
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
            f"$bmp.Save('{ps_safe_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose();"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and save_path.exists():
            return {
                "success": True,
                "path": str(save_path),
                "method": "PowerShell",
                "message": f"Screenshot saved: {save_path.name}",
            }
        raise RuntimeError(result.stderr.strip() or "PowerShell screenshot failed")
    except Exception as e:
        return {"success": False, "error": f"All screenshot methods failed. Last error: {e}"}


# ---------------------------------------------------------------------------
# Window capture
# ---------------------------------------------------------------------------

def capture_window(
    window_title: str,
    filename: Optional[str] = None,
    save_dir: Optional[str] = None,
) -> dict:
    """
    Capture a specific window by title (Windows only).

    Args:
        window_title: Partial or full title of the window to capture.
        filename:     Output filename stem; timestamped if None.
        save_dir:     Save directory; defaults to Desktop/JARVIS_Screenshots.

    Returns:
        dict with success, path, width, height, window_title, message or error.
    """
    save_path_dir = _ensure_save_dir(Path(save_dir) if save_dir else DEFAULT_SAVE_DIR)
    stem = filename or f"window_{window_title[:20].replace(' ', '_')}"
    save_path = save_path_dir / _timestamped_name(stem)

    # --- Method 1: PIL + win32gui ---
    try:
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        def _find_window(title_query: str) -> Optional[int]:
            hwnd_found = None
            def _enum(hwnd, _):
                nonlocal hwnd_found
                if title_query.lower() in win32gui.GetWindowText(hwnd).lower():
                    if win32gui.IsWindowVisible(hwnd):
                        hwnd_found = hwnd
            win32gui.EnumWindows(_enum, None)
            return hwnd_found

        hwnd = _find_window(window_title)
        if hwnd is None:
            raise RuntimeError(f"Window not found: '{window_title}'")

        # Bring window to front
        win32gui.SetForegroundWindow(hwnd)
        import time; time.sleep(0.3)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bmp)
        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
        bmp.SaveBitmapFile(save_dc, str(save_path.with_suffix(".bmp")))

        # Convert BMP -> PNG
        bmp_path = save_path.with_suffix(".bmp")
        img = Image.open(str(bmp_path))
        img.save(str(save_path), "PNG")
        bmp_path.unlink(missing_ok=True)

        # Cleanup
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        return {
            "success": True,
            "path": str(save_path),
            "width": width,
            "height": height,
            "window_title": win32gui.GetWindowText(hwnd),
            "method": "win32gui",
            "message": f"Window captured: {save_path.name}",
        }
    except ImportError:
        logger.debug("win32gui not available, falling back to full-screen crop")
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning("win32gui window capture failed: %s", e)

    # --- Method 2: Bring window to front + region grab via PIL ---
    try:
        import ctypes
        import time

        user32 = ctypes.windll.user32

        # Find window by title
        hwnd = user32.FindWindowW(None, window_title)
        if hwnd == 0:
            # Try partial match via EnumWindows
            matching = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            def _enum_cb(hwnd, _):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                if window_title.lower() in buf.value.lower() and user32.IsWindowVisible(hwnd):
                    matching.append(hwnd)
                return True

            user32.EnumWindows(_enum_cb, 0)
            hwnd = matching[0] if matching else 0

        if hwnd == 0:
            return {"success": False, "error": f"Window not found: '{window_title}'"}

        # Get window rect
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)

        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        img.save(str(save_path), "PNG")
        w, h = img.size
        return {
            "success": True,
            "path": str(save_path),
            "width": w,
            "height": h,
            "window_title": window_title,
            "method": "ctypes+PIL",
            "message": f"Window captured: {save_path.name}",
        }
    except Exception as e:
        logger.warning("ctypes+PIL window capture failed: %s", e)

    # Last resort: full screen capture
    logger.info("Falling back to full-screen capture for window: %s", window_title)
    result = capture_screen(filename=stem, save_dir=save_dir)
    if result["success"]:
        result["note"] = "Could not isolate window; captured full screen instead."
    return result


# ---------------------------------------------------------------------------
# Region capture
# ---------------------------------------------------------------------------

def capture_region(
    left: int,
    top: int,
    right: int,
    bottom: int,
    filename: Optional[str] = None,
    save_dir: Optional[str] = None,
) -> dict:
    """
    Capture a rectangular region of the screen.

    Args:
        left, top, right, bottom: Pixel coordinates of the region.
        filename: Output filename stem.
        save_dir: Save directory.

    Returns:
        dict with success, path, width, height, message or error.
    """
    save_path_dir = _ensure_save_dir(Path(save_dir) if save_dir else DEFAULT_SAVE_DIR)
    stem = filename or "region"
    save_path = save_path_dir / _timestamped_name(stem)

    bbox = (left, top, right, bottom)
    width = right - left
    height = bottom - top

    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=bbox)
        img.save(str(save_path), "PNG")
        return {
            "success": True,
            "path": str(save_path),
            "width": width,
            "height": height,
            "region": {"left": left, "top": top, "right": right, "bottom": bottom},
            "method": "PIL",
            "message": f"Region captured: {save_path.name}",
        }
    except ImportError:
        pass
    except Exception as e:
        logger.warning("PIL region capture failed: %s", e)

    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            mon = {"left": left, "top": top, "width": width, "height": height}
            img_data = sct.grab(mon)
            mss.tools.to_png(img_data.rgb, img_data.size, output=str(save_path))
        return {
            "success": True,
            "path": str(save_path),
            "width": width,
            "height": height,
            "method": "mss",
            "message": f"Region captured: {save_path.name}",
        }
    except Exception as e:
        return {"success": False, "error": f"Region capture failed: {e}"}


# ---------------------------------------------------------------------------
# List saved screenshots
# ---------------------------------------------------------------------------

def list_screenshots(save_dir: Optional[str] = None) -> dict:
    """List all screenshots in the save directory."""
    directory = Path(save_dir) if save_dir else DEFAULT_SAVE_DIR
    if not directory.exists():
        return {"success": True, "screenshots": [], "count": 0, "directory": str(directory)}

    screenshots = sorted(
        [
            {
                "name": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            }
            for f in directory.glob("*.png")
        ],
        key=lambda x: x["created"],
        reverse=True,
    )
    return {
        "success": True,
        "screenshots": screenshots,
        "count": len(screenshots),
        "directory": str(directory),
    }


# ---------------------------------------------------------------------------
# Convenience alias for system_control compatibility
# ---------------------------------------------------------------------------
take_screenshot = capture_screen
