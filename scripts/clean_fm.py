import re

with open("automation/file_manager.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = r'\n+class FileManagerResult:[\s\S]*?return FileManagerResult\(success=res\.get\("success", False\), message=msg, data=res\)'
cleaned = re.sub(pattern, '', content)

class_code = '''

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
'''

with open("automation/file_manager.py", "w", encoding="utf-8") as f:
    f.write(cleaned.strip() + class_code + "\n")

print("file_manager.py cleaned up successfully")
