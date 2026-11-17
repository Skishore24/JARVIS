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

SYSTEM_PROMPT: str = f"""You are {ASSISTANT_NAME}, an intelligent AI desktop assistant running on Windows.
You help users with tasks including file management, system monitoring, information lookup, task automation, and general questions.

When responding to user requests:
1. Be concise and helpful.
2. If a task requires executing actions (like opening apps, checking system stats, managing files), output a JSON block like:
   {{"intent": "TOOL_NAME", "params": {{...}}}}
3. Available tools: SYSTEM_MONITOR, OPEN_APP, FILE_OPERATION, WEB_SEARCH, NOTIFY, CHAT.
4. For plain conversation with no tool needed, use intent: "CHAT".
5. Always be professional and clear.

Current model: {OLLAMA_DEFAULT_MODEL}
"""
