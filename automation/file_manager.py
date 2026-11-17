"""
file_manager.py - Secure file management tools for JARVIS
Handles search, create, rename, move, copy, read and open operations.
"""

import os
import shutil
import logging
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default allowed directories (security whitelist)
# ---------------------------------------------------------------------------
_DEFAULT_ALLOWED: list[str] = [
    str(Path.home()),                            # User home
    str(Path.home() / "Documents"),
    str(Path.home() / "Downloads"),
    str(Path.home() / "Desktop"),
    str(Path.home() / "Pictures"),
    str(Path.home() / "Videos"),
    str(Path.home() / "Music"),
    r"C:\MyFiles",                               # Project area
]

ALLOWED_DIRECTORIES: list[Path] = [Path(d) for d in _DEFAULT_ALLOWED]

# Maximum file size to read into memory (10 MB)
MAX_READ_BYTES = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _is_path_allowed(path: Path | str) -> bool:
    """Return True only if resolved path is inside an allowed directory."""
    try:
        resolved = Path(path).resolve()
        return any(
            str(resolved).startswith(str(allowed.resolve()))
            for allowed in ALLOWED_DIRECTORIES
        )
    except Exception:
        return False


def _safe_resolve(path: str) -> Optional[Path]:
    """
    Resolve a path and validate it against the allowlist.
    Returns None if the path is outside allowed directories.
    """
    try:
        resolved = Path(path).resolve()
        if _is_path_allowed(resolved):
            return resolved
        logger.warning("Path traversal attempt blocked: %s", path)
        return None
    except Exception as e:
        logger.error("Path resolution error: %s", e)
        return None


def add_allowed_directory(directory: str) -> dict:
    """Dynamically add a directory to the security whitelist."""
    try:
        p = Path(directory).resolve()
        if p not in ALLOWED_DIRECTORIES:
            ALLOWED_DIRECTORIES.append(p)
        return {"success": True, "message": f"Added allowed directory: {p}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_files(
    query: str,
    directories: list[str] | None = None,
    extensions: list[str] | None = None,
    max_results: int = 50,
) -> dict:
    """
    Search for files matching query in given directories.

    Args:
        query:       Filename pattern or substring to match (case-insensitive).
        directories: Directories to search; defaults to ALLOWED_DIRECTORIES.
        extensions:  Filter by extensions e.g. ['.py', '.txt']; None = all.
        max_results: Maximum number of results to return.

    Returns:
        dict with success, results (list of file info dicts), count.
    """
    search_dirs = [Path(d) for d in directories] if directories else ALLOWED_DIRECTORIES
    query_lower = query.lower()

    # Normalise extensions
    if extensions:
        exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    else:
        exts = None

    results: list[dict] = []

    for search_dir in search_dirs:
        if not _is_path_allowed(search_dir):
            logger.warning("Skipping non-allowed search directory: %s", search_dir)
            continue
        if not search_dir.exists() or not search_dir.is_dir():
            continue

        try:
            for root, dirs, files in os.walk(search_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    if query_lower in fname.lower():
                        file_path = Path(root) / fname
                        if exts and file_path.suffix.lower() not in exts:
                            continue
                        try:
                            stat = file_path.stat()
                            results.append({
                                "name": fname,
                                "path": str(file_path),
                                "size_bytes": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "extension": file_path.suffix,
                            })
                        except OSError:
                            continue
                        if len(results) >= max_results:
                            return {
                                "success": True,
                                "results": results,
                                "count": len(results),
                                "truncated": True,
                            }
        except PermissionError:
            continue
        except Exception as e:
            logger.error("Search error in %s: %s", search_dir, e)

    return {
        "success": True,
        "results": results,
        "count": len(results),
        "truncated": False,
    }


# ---------------------------------------------------------------------------
# Directory / File creation
# ---------------------------------------------------------------------------

def create_folder(path: str) -> dict:
    """Create a directory (and all parents)."""
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    try:
        safe.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(safe), "message": f"Folder created: {safe}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



def create_file(path: str, content: str = "", encoding: str = "utf-8") -> dict:
    """Create a text file with optional content."""
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding=encoding)
        return {"success": True, "path": str(safe), "message": f"File created: {safe}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



# ---------------------------------------------------------------------------
# Rename / Move / Copy
# ---------------------------------------------------------------------------

def rename_file(old_path: str, new_path: str) -> dict:
    """Rename a file or folder."""
    old = _safe_resolve(old_path)
    new = _safe_resolve(new_path)

    if old is None:
        return {"success": False, "error": f"Source path not allowed: {old_path}"}
    if new is None:
        return {"success": False, "error": f"Destination path not allowed: {new_path}"}
    if not old.exists():
        return {"success": False, "error": f"Source does not exist: {old}"}
    if new.exists():
        return {"success": False, "error": f"Destination already exists: {new}"}
    try:
        old.rename(new)
        return {"success": True, "old": str(old), "new": str(new), "message": f"Renamed to {new.name}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



def move_file(src: str, dst: str) -> dict:
    """Move a file or folder to a new location."""
    src_path = _safe_resolve(src)
    dst_path = _safe_resolve(dst)

    if src_path is None:
        return {"success": False, "error": f"Source path not allowed: {src}"}
    if dst_path is None:
        return {"success": False, "error": f"Destination path not allowed: {dst}"}
    if not src_path.exists():
        return {"success": False, "error": f"Source does not exist: {src_path}"}
    try:
        shutil.move(str(src_path), str(dst_path))
        return {"success": True, "src": str(src_path), "dst": str(dst_path), "message": f"Moved to {dst_path}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except shutil.Error as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



def copy_file(src: str, dst: str) -> dict:
    """Copy a file or directory tree to a new location."""
    src_path = _safe_resolve(src)
    dst_path = _safe_resolve(dst)

    if src_path is None:
        return {"success": False, "error": f"Source path not allowed: {src}"}
    if dst_path is None:
        return {"success": False, "error": f"Destination path not allowed: {dst}"}
    if not src_path.exists():
        return {"success": False, "error": f"Source does not exist: {src_path}"}
    try:
        if src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path))
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
        return {"success": True, "src": str(src_path), "dst": str(dst_path), "message": f"Copied to {dst_path}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except shutil.Error as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



# ---------------------------------------------------------------------------
# Read / Open
# ---------------------------------------------------------------------------

def read_file(path: str, encoding: str = "utf-8") -> dict:
    """
    Read a text file safely.

    Returns:
        dict with success, content (str), size_bytes, encoding.
    """
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    if not safe.exists():
        return {"success": False, "error": f"File does not exist: {safe}"}
    if not safe.is_file():
        return {"success": False, "error": f"Path is not a file: {safe}"}

    size = safe.stat().st_size
    if size > MAX_READ_BYTES:
        return {
            "success": False,
            "error": f"File too large to read ({size / (1024*1024):.1f} MB). Max is {MAX_READ_BYTES // (1024*1024)} MB.",
        }
    try:
        content = safe.read_text(encoding=encoding)
        return {
            "success": True,
            "path": str(safe),
            "content": content,
            "size_bytes": size,
            "encoding": encoding,
        }
    except UnicodeDecodeError:
        # Try latin-1 as fallback
        try:
            content = safe.read_text(encoding="latin-1")
            return {
                "success": True,
                "path": str(safe),
                "content": content,
                "size_bytes": size,
                "encoding": "latin-1",
                "note": "Decoded with latin-1 fallback",
            }
        except Exception as e:
            return {"success": False, "error": f"Could not decode file: {e}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



def open_file(path: str) -> dict:
    """Open a file with the default associated application."""
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    if not safe.exists():
        return {"success": False, "error": f"File does not exist: {safe}"}
    try:
        os.startfile(str(safe))  # Windows-specific
        return {"success": True, "path": str(safe), "message": f"Opened: {safe.name}"}
    except Exception as e:
        # Fallback via explorer
        try:
            import subprocess
            subprocess.Popen(["explorer.exe", str(safe)])
            return {"success": True, "path": str(safe), "message": f"Opened via Explorer: {safe.name}"}
        except Exception as e2:
            return {"success": False, "error": f"Could not open file: {e} / {e2}"}


def open_folder(path: str) -> dict:
    """Open a folder in Windows Explorer."""
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    target = safe if safe.is_dir() else safe.parent
    try:
        import subprocess
        subprocess.Popen(["explorer.exe", str(target)])
        return {"success": True, "path": str(target), "message": f"Opened folder: {target}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)



# ---------------------------------------------------------------------------
# List files
# ---------------------------------------------------------------------------

def list_files(directory: str, include_hidden: bool = False) -> dict:
    """
    List files and folders in a directory.

    Returns:
        dict with success, items (list of dicts), count.
    """
    safe = _safe_resolve(directory)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {directory}"}
    if not safe.exists():
        return {"success": False, "error": f"Directory does not exist: {safe}"}
    if not safe.is_dir():
        return {"success": False, "error": f"Path is not a directory: {safe}"}

    items: list[dict] = []
    try:
        for entry in sorted(safe.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if not include_hidden and entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "file" if entry.is_file() else "folder",
                    "size_bytes": stat.st_size if entry.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": entry.suffix if entry.is_file() else "",
                })
            except OSError:
                continue
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)


    return {
        "success": True,
        "directory": str(safe),
        "items": items,
        "count": len(items),
    }


# ---------------------------------------------------------------------------
# Delete (requires explicit confirmation)
# ---------------------------------------------------------------------------

def delete_file(path: str, confirmed: bool = False) -> dict:
    """
    Delete a file or folder.

    Args:
        path:      Path to delete.
        confirmed: MUST be True to actually delete. Safety guard.
    """
    if not confirmed:
        return {
            "success": False,
            "error": "Deletion requires explicit confirmation. Pass confirmed=True to proceed.",
        }
    safe = _safe_resolve(path)
    if safe is None:
        return {"success": False, "error": f"Path not allowed or invalid: {path}"}
    if not safe.exists():
        return {"success": False, "error": f"Path does not exist: {safe}"}
    try:
        if safe.is_dir():
            shutil.rmtree(str(safe))
        else:
            safe.unlink()
        return {"success": True, "deleted": str(safe), "message": f"Deleted: {safe.name}"}
    except PermissionError as e:
        return {"success": False, "error": f"Permission denied: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

class FileManagerResult:
    """Wrapper result object for FileManager methods."""
    def __init__(self, success: bool, message: str, data: dict | None = None) -> None:
        self.success = success
        self.message = message
        self.data = data or {}

    def __repr__(self) -> str:
        return f"<FileManagerResult success={self.success} message='{self.message}'>"


class FileManager:
    """Object-oriented interface for file and directory management."""

    def search_files(self, query: str, directory: str = "", extensions: list[str] | None = None) -> FileManagerResult:
        res = search_files(query, directory or None, extensions)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_folder(self, path: str) -> FileManagerResult:
        res = create_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def create_file(self, path: str, content: str = "") -> FileManagerResult:
        res = create_file(path, content)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_file(self, path: str) -> FileManagerResult:
        res = open_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def open_folder(self, path: str) -> FileManagerResult:
        res = open_folder(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def read_file(self, path: str) -> FileManagerResult:
        res = read_file(path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def list_files(self, directory: str = "") -> FileManagerResult:
        res = list_files(directory or None)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def rename_file(self, old_path: str, new_path: str) -> FileManagerResult:
        res = rename_file(old_path, new_path)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def move_file(self, src: str, dst: str) -> FileManagerResult:
        res = move_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

    def copy_file(self, src: str, dst: str) -> FileManagerResult:
        res = copy_file(src, dst)
        msg = res.get("message") or res.get("error", "")
        return FileManagerResult(success=res.get("success", False), message=msg, data=res)

