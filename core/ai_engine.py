"""
core/ai_engine.py
-----------------
Ollama LLM integration with streaming support and conversation context management.
Uses the official `ollama` Python library in a thread-safe manner.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Generator
from typing import Any

import ollama

import config

logger = logging.getLogger(__name__)


class AIEngine:
    """
    Wraps the Ollama client to provide:
    - Streaming chat completions
    - Non-streaming chat completions
    - Intent extraction (JSON parsing from model output)
    - Thread-safe model switching
    """

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._model = model or config.OLLAMA_DEFAULT_MODEL
        self._host = host or config.OLLAMA_HOST
        self._system_prompt = system_prompt or config.SYSTEM_PROMPT
        self._lock = threading.Lock()

        # Initialize the client
        self._client = ollama.Client(host=self._host)
        logger.info("AIEngine initialised — model=%s host=%s", self._model, self._host)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        with self._lock:
            logger.info("Switching model from %s to %s", self._model, value)
            self._model = value

    # ── Core Chat ─────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Send a chat request to Ollama.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
                      System prompt is prepended automatically.
            stream:   If True, return a generator of text chunks.

        Returns:
            Full response string (stream=False) or chunk generator (stream=True).
        """
        full_messages = self._build_messages(messages)

        with self._lock:
            model = self._model

        if stream:
            return self._stream_chat(full_messages, model)
        return self._blocking_chat(full_messages, model)

    def _build_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Prepend the system prompt unless already present."""
        if messages and messages[0].get("role") == "system":
            return messages
        return [{"role": "system", "content": self._system_prompt}] + messages

    def _blocking_chat(
        self, messages: list[dict[str, str]], model: str
    ) -> str:
        """Non-streaming chat; returns the complete assistant reply."""
        try:
            response = self._client.chat(
                model=model,
                messages=messages,
                options={"num_predict": config.OLLAMA_MAX_TOKENS},
            )
            content: str = response["message"]["content"]
            logger.debug("AI response (%d chars): %.120s…", len(content), content)
            return content
        except ollama.ResponseError as exc:
            logger.error("Ollama ResponseError: %s", exc)
            raise RuntimeError(f"Ollama error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected AI engine error: %s", exc)
            raise

    def _stream_chat(
        self, messages: list[dict[str, str]], model: str
    ) -> Generator[str, None, None]:
        """Streaming chat; yields text chunks as they arrive."""
        try:
            stream = self._client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={"num_predict": config.OLLAMA_MAX_TOKENS},
            )
            for chunk in stream:
                delta: str = chunk.get("message", {}).get("content", "")
                if delta:
                    yield delta
        except ollama.ResponseError as exc:
            logger.error("Ollama stream ResponseError: %s", exc)
            raise RuntimeError(f"Ollama stream error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected stream error: %s", exc)
            raise

    # ── Intent Extraction ─────────────────────────────────────────────────────

    def extract_intent(self, ai_response: str) -> dict[str, Any] | None:
        """
        Parse a JSON intent block from the AI response text.

        The model is prompted to emit blocks like:
            {"intent": "TOOL_NAME", "params": {...}}

        Returns the parsed dict or None if no valid JSON block found.
        """
        # Try to find the first {...} block
        start = ai_response.find("{")
        end = ai_response.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        candidate = ai_response[start:end]
        try:
            parsed: dict[str, Any] = json.loads(candidate)
            if "intent" in parsed:
                logger.debug("Extracted intent: %s", parsed.get("intent"))
                return parsed
        except json.JSONDecodeError:
            logger.debug("No valid JSON intent block in response.")
        return None

    # ── Utility ───────────────────────────────────────────────────────────────

    def list_local_models(self) -> list[str]:
        """Return names of all locally available Ollama models."""
        try:
            result = self._client.list()
            models_list = getattr(result, "models", None)
            if models_list is not None:
                return [getattr(m, "model", None) or getattr(m, "name", str(m)) for m in models_list]
            if isinstance(result, dict):
                return [m.get("name") or m.get("model") for m in result.get("models", [])]
            return []
        except Exception as exc:
            logger.error("Could not list models: %s", exc)
            return []

    def is_model_available(self, model_name: str | None = None) -> bool:
        """Check whether a model (default: configured model) is pulled locally."""
        name = model_name or self._model
        return any(name in m for m in self.list_local_models())

    def health_check(self) -> bool:
        """Ping Ollama to verify the server is reachable."""
        try:
            self._client.list()
            return True
        except Exception:
            return False
