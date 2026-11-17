"""
core/assistant.py
-----------------
Main JARVIS orchestrator — the entry point for all user interactions.

Wires together:
  AIEngine → TaskPlanner → ExecutionEngine → CommandRouter
  MemoryManager → ConversationHistory
  PermissionManager
  SystemMonitor + NotificationService

Runs the main chat loop in a background thread.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Generator
from typing import Any

import config
from core.ai_engine import AIEngine
from core.command_router import CommandRouter
from core.execution_engine import ExecutionEngine
from core.permission_manager import PermissionManager
from core.task_planner import TaskPlan, TaskPlanner
from memory.memory_manager import MemoryManager
from services.notification_service import NotificationService
from services.system_monitor import SystemMonitor

logger = logging.getLogger(__name__)


class Assistant:
    """
    Top-level JARVIS assistant.

    Typical usage:
        assistant = Assistant()
        assistant.start()
        response = assistant.chat("What is my CPU usage?")
        assistant.stop()

    For streaming:
        for chunk in assistant.stream_chat("Tell me a story"):
            print(chunk, end="", flush=True)
    """

    def __init__(self) -> None:
        logger.info("Initialising JARVIS assistant…")

        # Subsystems
        self._monitor = SystemMonitor()
        self._notifier = NotificationService()
        self._permission_manager = PermissionManager()
        self._memory = MemoryManager()
        self._ai = AIEngine()
        self._router = CommandRouter(
            permission_manager=self._permission_manager,
            system_monitor=self._monitor,
            notification_service=self._notifier,
        )
        self._planner = TaskPlanner(ai_engine=self._ai)
        self._executor = ExecutionEngine(command_router=self._router)

        # State
        self._session_id: str = self._memory.new_session()
        self._running = False
        self._lock = threading.Lock()

        logger.info(
            "JARVIS initialised — session=%s model=%s",
            self._session_id,
            self._ai.model,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Mark the assistant as active and greet the user."""
        self._running = True
        logger.info("JARVIS started.")
        greeting = (
            f"Hello! I'm {config.ASSISTANT_NAME}, your AI desktop assistant. "
            "How can I help you today?"
        )
        self._memory.add_message(self._session_id, "assistant", greeting)

    def stop(self) -> None:
        """Gracefully shut down the assistant."""
        self._running = False
        self._memory.close()
        logger.info("JARVIS stopped.")

    # ── Chat Interface ────────────────────────────────────────────────────────

    def chat(self, user_input: str) -> str:
        """
        Process a user message and return the full response string.

        Pipeline:
        1. Save user message to memory.
        2. Build conversation context.
        3. Send to AI for intent extraction + response.
        4. If a tool intent was found, plan & execute.
        5. Save assistant reply to memory.
        6. Return reply.
        """
        with self._lock:
            return self._process(user_input, stream=False)  # type: ignore[return-value]

    def stream_chat(self, user_input: str) -> Generator[str, None, None]:
        """
        Process a user message and stream the response in chunks.

        Note: tool execution results are yielded as a single final chunk.
        """
        with self._lock:
            yield from self._process(user_input, stream=True)  # type: ignore[misc]

    # ── Core Processing ───────────────────────────────────────────────────────

    def _process(
        self, user_input: str, stream: bool
    ) -> str | Generator[str, None, None]:
        """Internal processing pipeline."""
        logger.debug("Processing user input: %.80s", user_input)

        # 1. Persist user turn
        self._memory.add_message(self._session_id, "user", user_input)

        # 2. Build context (last N messages as ollama-format dicts)
        history = self._memory.get_recent_messages(
            self._session_id, limit=config.MAX_CONVERSATION_HISTORY
        )
        context = [{"role": m.role, "content": m.content} for m in history]

        # 3. Get AI response (non-streaming for intent extraction first)
        ai_response = self._ai.chat(context, stream=False)
        assert isinstance(ai_response, str)

        # 4. Check for a tool intent
        intent_data = self._ai.extract_intent(ai_response)
        reply: str

        if intent_data and intent_data.get("intent", "CHAT") != "CHAT":
            intent = intent_data["intent"]
            params = intent_data.get("params", {})
            logger.info("Routing intent: %s", intent)

            # Use TaskPlanner for complex actions; direct dispatch for simple ones
            if self._is_multi_step(intent, params):
                plan: TaskPlan = self._planner.create_plan(user_input, context)
                reply = self._executor.execute(plan)
            else:
                reply = self._router.dispatch(intent, params)
        else:
            # Plain conversational response
            clean_text = self._clean_chat_reply(ai_response, intent_data)
            if stream:
                def _gen() -> Generator[str, None, None]:
                    # Yield the cleaned text
                    self._memory.add_message(self._session_id, "assistant", clean_text)
                    yield clean_text

                return _gen()
            reply = clean_text

        # 5. Persist assistant reply
        self._memory.add_message(self._session_id, "assistant", reply)

        if stream:
            def _single() -> Generator[str, None, None]:
                yield reply

            return _single()

        return reply

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_chat_reply(ai_response: str, intent_data: dict[str, Any] | None = None) -> str:
        """Strip internal JSON routing headers and return clean human text."""
        if intent_data:
            if "response" in intent_data and isinstance(intent_data["response"], str):
                return intent_data["response"].strip()
            if "message" in intent_data and isinstance(intent_data["message"], str):
                return intent_data["message"].strip()

        import re
        cleaned = re.sub(r'^\s*\{[^{}]*"intent"[^{}]*\}\s*', '', ai_response).strip()
        cleaned = re.sub(r'\s*\{[^{}]*"intent"[^{}]*\}\s*$', '', cleaned).strip()
        cleaned = re.sub(r'(?i)\n*\s*intent\s*:\s*[A-Z_]+\s*$', '', cleaned).strip()

        # If text remains after stripping the intent JSON, return it
        if cleaned:
            # Further strip any stray JSON brackets
            cleaned = re.sub(r'^\s*\{[^{}]*\}\s*', '', cleaned).strip()
            if cleaned:
                return cleaned

        # If the model only emitted a blank CHAT intent block or empty string
        return "Hello! I am JARVIS, your AI assistant. How can I help you today?"

    @staticmethod
    def _is_multi_step(intent: str, params: dict[str, Any]) -> bool:
        """
        Heuristic: decide whether to invoke the full task planner.
        Currently only specific complex intents trigger planning.
        """
        multi_step_intents = {"MULTI_STEP", "AUTOMATION", "PIPELINE"}
        return intent.upper() in multi_step_intents

    def health_check(self) -> dict[str, Any]:
        """Return a health summary of all subsystems."""
        return {
            "ollama_reachable": self._ai.health_check(),
            "model": self._ai.model,
            "session_id": self._session_id,
            "permissions": self._permission_manager.get_permission_summary(),
            "system": self._monitor.get_full_report(),
        }

    def switch_model(self, model_name: str) -> str:
        """Hot-swap the LLM model."""
        self._ai.model = model_name
        return f"✅ Switched to model '{model_name}'."

    def get_session_id(self) -> str:
        return self._session_id
