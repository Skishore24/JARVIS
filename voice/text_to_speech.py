"""
voice/text_to_speech.py
------------------------
pyttsx3-based Text-to-Speech with queue, threading, and interrupt support.
Fully offline, no model downloads needed. Uses Windows SAPI voices.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.error("pyttsx3 not installed – TTS unavailable. Run: pip install pyttsx3")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class TTSState(Enum):
    IDLE = auto()
    SPEAKING = auto()
    PAUSED = auto()
    STOPPED = auto()


@dataclass
class TTSConfig:
    rate: int = 175                    # words per minute (pyttsx3 default ~200)
    volume: float = 0.9               # 0.0 – 1.0
    voice_index: Optional[int] = None # None = system default
    voice_id: Optional[str] = None    # specific voice ID string
    max_queue_size: int = 20
    pre_speech_delay_s: float = 0.0   # delay before each utterance
    post_speech_delay_s: float = 0.1  # delay after each utterance


@dataclass
class _TTSRequest:
    text: str
    priority: int = 0                 # higher = spoken sooner
    callback: Optional[Callable[[], None]] = None
    request_id: int = 0


# ---------------------------------------------------------------------------
# TTS Engine
# ---------------------------------------------------------------------------

class TextToSpeech:
    """
    Non-blocking TTS using pyttsx3 running in a dedicated daemon thread.

    Features
    --------
    - Queue-based: speak() returns immediately
    - Priority queue: urgent responses jump the queue
    - interrupt(): stop current speech and clear queue
    - Configurable rate, volume, and voice
    - State callbacks for UI integration

    Usage
    -----
    >>> tts = TextToSpeech()
    >>> tts.start()
    >>> tts.speak("Hello, I am JARVIS.")
    >>> tts.speak("Priority message.", priority=10)
    >>> tts.interrupt()
    >>> tts.stop()
    """

    def __init__(self, config: Optional[TTSConfig] = None) -> None:
        self.config = config or TTSConfig()
        self._engine: Optional[pyttsx3.Engine] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: queue.PriorityQueue[tuple[int, _TTSRequest]] = queue.PriorityQueue(
            maxsize=self.config.max_queue_size
        )
        self._running = False
        self._state = TTSState.IDLE
        self._state_lock = threading.Lock()
        self._interrupt_event = threading.Event()
        self._state_callbacks: list[Callable[[TTSState], None]] = []
        self._request_counter = 0
        self._counter_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Voices
    # ------------------------------------------------------------------

    @staticmethod
    def list_voices() -> list[dict]:
        """Return available SAPI voices (name, id, languages)."""
        if not PYTTSX3_AVAILABLE:
            return []
        try:
            engine = pyttsx3.init()
            voices = []
            for i, v in enumerate(engine.getProperty("voices")):
                voices.append({
                    "index": i,
                    "id": v.id,
                    "name": v.name,
                    "languages": v.languages,
                    "gender": v.gender,
                    "age": v.age,
                })
            engine.stop()
            return voices
        except Exception as exc:
            logger.error("Error listing voices: %s", exc)
            return []

    # ------------------------------------------------------------------
    # State callbacks (for UI / Qt signals)
    # ------------------------------------------------------------------

    def add_state_callback(self, cb: Callable[[TTSState], None]) -> None:
        self._state_callbacks.append(cb)

    def _set_state(self, state: TTSState) -> None:
        with self._state_lock:
            if self._state == state:
                return
            self._state = state
        for cb in self._state_callbacks:
            try:
                cb(state)
            except Exception:
                pass

    @property
    def state(self) -> TTSState:
        with self._state_lock:
            return self._state

    @property
    def is_speaking(self) -> bool:
        return self.state == TTSState.SPEAKING

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Initialise pyttsx3 and launch the worker thread. Returns True on success."""
        if not PYTTSX3_AVAILABLE:
            logger.error("pyttsx3 not available")
            return False
        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(
            target=self._worker, name="TTS-Worker", daemon=True
        )
        self._thread.start()
        logger.info("TTS engine started")
        return True

    def stop(self) -> None:
        """Stop the TTS engine and worker thread."""
        self._running = False
        self.interrupt()
        # Unblock the worker
        try:
            self._queue.put_nowait((-9999, _TTSRequest(text="__STOP__")))
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3.0)
        self._thread = None
        self._set_state(TTSState.STOPPED)
        logger.info("TTS engine stopped")

    def speak(
        self,
        text: str,
        priority: int = 0,
        callback: Optional[Callable[[], None]] = None,
    ) -> int:
        """
        Queue text for speech. Returns a request ID.

        Parameters
        ----------
        text:
            The text to speak.
        priority:
            Higher priority requests are spoken before lower ones.
            Use positive integers for urgent messages.
        callback:
            Called (in the TTS thread) when this utterance finishes.
        """
        if not text or not text.strip():
            return -1
        if not self._running:
            logger.warning("TTS not running – call start() first")
            return -1

        with self._counter_lock:
            self._request_counter += 1
            req_id = self._request_counter

        req = _TTSRequest(text=text.strip(), priority=priority,
                          callback=callback, request_id=req_id)
        # Priority queue: lower number = higher priority → negate priority
        try:
            self._queue.put_nowait((-priority, req))
            logger.debug("TTS queued [%d] '%s…'", req_id, text[:40])
        except queue.Full:
            logger.warning("TTS queue full – dropping: '%s…'", text[:30])
            return -1
        return req_id

    def speak_now(self, text: str) -> int:
        """Interrupt current speech and immediately speak text (priority=999)."""
        self.interrupt()
        return self.speak(text, priority=999)

    def interrupt(self) -> None:
        """Stop current speech immediately and discard the pending queue."""
        self._interrupt_event.set()
        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.debug("TTS interrupted")

    def set_rate(self, rate: int) -> None:
        """Change speech rate (words per minute). Takes effect on next utterance."""
        self.config.rate = rate

    def set_volume(self, volume: float) -> None:
        """Change volume (0.0–1.0). Takes effect on next utterance."""
        self.config.volume = max(0.0, min(1.0, volume))

    def set_voice(self, index: Optional[int] = None, voice_id: Optional[str] = None) -> None:
        """Select a voice by index or ID. Takes effect on next utterance."""
        self.config.voice_index = index
        self.config.voice_id = voice_id

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        """Main TTS loop – runs in a dedicated thread."""
        try:
            self._engine = pyttsx3.init()
            self._apply_config()
        except Exception as exc:
            logger.error("Failed to init pyttsx3: %s", exc)
            self._running = False
            return

        logger.debug("TTS worker ready")

        while self._running:
            try:
                _, req = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if req.text == "__STOP__":
                break

            # Clear any previous interrupt signal
            self._interrupt_event.clear()

            if self.config.pre_speech_delay_s > 0:
                time.sleep(self.config.pre_speech_delay_s)

            # Re-apply config in case it changed
            self._apply_config()

            self._set_state(TTSState.SPEAKING)
            logger.debug("TTS speaking [%d]: '%s…'", req.request_id, req.text[:50])

            try:
                self._engine.say(req.text)

                # runAndWait blocks until done; we check interrupt flag via onWord
                self._engine.connect("started-word", self._on_word)
                self._engine.runAndWait()

            except Exception as exc:
                logger.error("pyttsx3 error: %s", exc)
                # Re-create engine on error
                try:
                    self._engine = pyttsx3.init()
                    self._apply_config()
                except Exception:
                    pass

            if req.callback:
                try:
                    req.callback()
                except Exception:
                    pass

            self._set_state(TTSState.IDLE)

            if self.config.post_speech_delay_s > 0:
                time.sleep(self.config.post_speech_delay_s)

        # Cleanup
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass
        logger.debug("TTS worker exited")

    def _on_word(self, name: str, location: int, length: int) -> None:
        """Called by pyttsx3 for each word – used to check for interrupt."""
        if self._interrupt_event.is_set():
            try:
                self._engine.stop()
            except Exception:
                pass

    def _apply_config(self) -> None:
        """Push current config settings to the pyttsx3 engine."""
        if not self._engine:
            return
        try:
            self._engine.setProperty("rate", self.config.rate)
            self._engine.setProperty("volume", self.config.volume)

            voices = self._engine.getProperty("voices")
            if voices:
                if self.config.voice_id:
                    # Find by ID
                    for v in voices:
                        if v.id == self.config.voice_id:
                            self._engine.setProperty("voice", v.id)
                            break
                elif self.config.voice_index is not None:
                    idx = min(self.config.voice_index, len(voices) - 1)
                    self._engine.setProperty("voice", voices[idx].id)
                else:
                    # Default to female voice (Zira / female tag)
                    female_voice_id = None
                    for v in voices:
                        name_lower = v.name.lower()
                        id_lower = v.id.lower()
                        gender_str = str(getattr(v, "gender", "") or "").lower()
                        if "zira" in name_lower or "female" in gender_str or "zira" in id_lower or "hazel" in name_lower or "eva" in name_lower:
                            female_voice_id = v.id
                            break
                    if not female_voice_id and len(voices) > 1:
                        female_voice_id = voices[1].id
                    if female_voice_id:
                        self._engine.setProperty("voice", female_voice_id)
        except Exception as exc:
            logger.debug("apply_config error: %s", exc)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "TextToSpeech":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Available voices:")
    for v in TextToSpeech.list_voices():
        print(f"  [{v['index']}] {v['name']}")

    tts = TextToSpeech(TTSConfig(rate=170, volume=0.9))
    with tts:
        tts.speak("Hello! I am JARVIS, your AI desktop assistant.")
        time.sleep(3)
        tts.speak("I can speak to you in real time.")
        time.sleep(2)
        tts.interrupt()
        tts.speak("Speech was interrupted. Have a great day!")
        time.sleep(4)
    print("TTS test complete.")
