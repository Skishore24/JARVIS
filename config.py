"""
JARVIS AI Desktop Assistant - Configuration Module
Loads and validates all configuration from environment variables.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).parent
load_dotenv(_PROJECT_ROOT / ".env")


# ─── Paths ───────────────────────────────────────────────────────────────────

PROJECT_ROOT: Path = _PROJECT_ROOT
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
DATABASE_PATH: Path = DATA_DIR / "jarvis.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


# ─── Ollama ───────────────────────────────────────────────────────────────────

OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "4096"))


# ─── Database ────────────────────────────────────────────────────────────────

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", f"sqlite:///{DATABASE_PATH}"
)


# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE: str = os.getenv("LOG_FILE", str(LOGS_DIR / "jarvis.log"))


def setup_logging() -> logging.Logger:
    """Configure root logger for JARVIS."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )
    return logging.getLogger("jarvis")


# ─── Assistant ────────────────────────────────────────────────────────────────

ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "JARVIS")
MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))
TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))


# ─── Permissions ─────────────────────────────────────────────────────────────

ALLOW_FILE_SYSTEM_ACCESS: bool = os.getenv("ALLOW_FILE_SYSTEM_ACCESS", "true").lower() == "true"
ALLOW_PROCESS_EXECUTION: bool = os.getenv("ALLOW_PROCESS_EXECUTION", "true").lower() == "true"
ALLOW_NETWORK_ACCESS: bool = os.getenv("ALLOW_NETWORK_ACCESS", "true").lower() == "true"
ALLOW_SYSTEM_SETTINGS: bool = os.getenv("ALLOW_SYSTEM_SETTINGS", "false").lower() == "true"


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT: str = f"""You are {ASSISTANT_NAME}, an intelligent, polite AI desktop assistant running on Windows.
You help users with tasks including opening applications, checking system resources, managing files, web searches, answering questions, and general conversation.

Guidelines:
1. For normal questions, greetings ("hi", "hello"), or conversation, respond directly and naturally in plain English. Do NOT output JSON for normal chat or greetings.
2. Only output a tool action when the user explicitly asks you to perform a computer action (like opening an application, checking system stats, creating a file, searching Google).
3. When performing a tool action, output:
   {{"intent": "TOOL_NAME", "params": {{...}}}}
4. Available tools:
   - OPEN_APP: {{"app": "name of application (e.g. notepad, chrome, vscode, calc)"}}
   - SYSTEM_MONITOR: {{"metric": "all" | "cpu" | "ram" | "battery" | "disk"}}
   - FILE_OPERATION: {{"action": "create"|"read"|"list"|"delete", "path": "path", "content": "text"}}
   - WEB_SEARCH: {{"query": "search query"}}
   - NOTIFY: {{"title": "title", "message": "text"}}
5. Be concise, friendly, and helpful.
"""
