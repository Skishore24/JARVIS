"""
voice/audio_manager.py
----------------------
Central coordinator for all voice/audio components.

State machine:
  IDLE → LISTENING → PROCESSING → SPEAKING → IDLE

Qt signals are emitted on state transitions; the class works without Qt
(signals are no-ops when PySide6 is not available).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

import numpy as np

from .microphone import Microphone, MicrophoneConfig, AudioChunk
from .speech_to_text import SpeechToText, STTConfig, TranscriptionResult
from .text_to_speech import TextToSpeech, TTSConfig, TTSState
from .wake_word import WakeWordDetector, WakeWordConfig, WakeWordResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Qt integration
# ---------------------------------------------------------------------------
try:
    from PySide6.QtCore import QObject, Signal

    class _Signals(QObject):
        state_changed = Signal(str)           # new state name
        transcription_ready = Signal(str, float)  # text, confidence
        wake_word_detected = Signal(str)       # phrase
        audio_level_changed = Signal(float)   # 0-1
        tts_state_changed = Signal(str)       # TTS state name
        error_occurred = Signal(str)          # error message

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class _Signals:  # type: ignore[no-redef]
        """Stub when PySide6 is absent."""
        def __init__(self):
            pass
        def emit(self, *a, **kw): pass
        # Allow attribute access to signal names without error
        def __getattr__(self, _): return self


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class AudioState(Enum):
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


@dataclass
class AudioManagerConfig:
    microphone: MicrophoneConfig = field(default_factory=MicrophoneConfig)
    stt: STTConfig = field(default_factory=lambda: STTConfig(model_size="base"))
    tts: TTSConfig = field(default_factory=TTSConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    require_wake_word: bool = False      # if False, listen directly to commands when mic is active
    auto_start_listening: bool = True   # re-enter LISTENING after SPEAKING
    stt_queue_size: int = 5             # max queued utterances for transcription
    mute_mic_while_speaking: bool = True  # prevents TTS echo


# ---------------------------------------------------------------------------
# Audio Manager
# ---------------------------------------------------------------------------

class AudioManager:
    """
    Coordinates Microphone → WakeWord → STT → TTS in a thread-safe state machine.

    Callback hooks
    --------------
    on_command(text, confidence)  – called when a transcription passes wake word check
    on_transcription(result)      – called for every STT result (wake word or not)
    on_state_change(state)        – called on every state transition
    """

    def __init__(
        self,
        config: Optional[AudioManagerConfig] = None,
        parent=None,
    ) -> None:
        self.config = config or AudioManagerConfig()

        # Sub-systems
        self.microphone = Microphone(self.config.microphone)
        self.stt = SpeechToText(self.config.stt)
        self.tts = TextToSpeech(self.config.tts)
        self.wake_detector = WakeWordDetector(self.config.wake_word)

        # State
        self._state = AudioState.IDLE
        self._state_lock = threading.Lock()
        self._is_running = False

        # Qt signals (or no-op stubs)
        if QT_AVAILABLE and parent is not None:
            self.signals = _Signals(parent)
        else:
            self.signals = _Signals()

        # Transcription worker
        self._stt_queue: queue.Queue[list[AudioChunk]] = queue.Queue(
            maxsize=self.config.stt_queue_size
        )
        self._stt_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_command: Optional[Callable[[str, float], None]] = None
        self.on_transcription: Optional[Callable[[TranscriptionResult], None]] = None
        self.on_state_change: Optional[Callable[[AudioState], None]] = None

        # Plumbing
        self._wire_callbacks()

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _wire_callbacks(self) -> None:
        """Connect sub-system events to our handlers."""
        # Microphone → level updates
        self.microphone.set_level_callback(self._on_audio_level)
        # Microphone → VAD utterance detected
        self.microphone.set_vad_start_callback(self._on_vad_start)
        self.microphone.set_vad_end_callback(self._on_vad_end)
        # TTS → state changes
        self.tts.add_state_callback(self._on_tts_state_change)
        # Wake word
        self.wake_detector.on_wake_word = self._on_wake_word

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start microphone and STT pipeline. Returns True if started successfully."""
        if self._is_running:
            return True

        logger.info("AudioManager: starting…")
        success = True

        # Load Whisper (if not already loaded)
        if not getattr(self.stt, "_loaded", False):
            if not self.stt.load():
                logger.error("STT model failed to load")
                success = False

        # Load wake word (optional)
        self.wake_detector.load()  # gracefully degrades to text-match

        # Start TTS if not running
        if not self.tts.is_running:
            if not self.tts.start():
                logger.error("TTS engine failed to start")
                success = False

        # Start microphone
        if not self.microphone.start():
            logger.error("Microphone failed to start")
            success = False

        # Start STT worker thread
        self._is_running = True
        self._stt_thread = threading.Thread(
            target=self._stt_worker, name="STT-Worker", daemon=True
        )
        self._stt_thread.start()

        self._transition(AudioState.LISTENING if success else AudioState.ERROR)
        logger.info("AudioManager: started (state=%s)", self._state.name)
        return success

    def stop(self) -> None:
        """Stop microphone listening gracefully (keeps TTS running for voice output)."""
        if not self._is_running:
            return
        logger.info("AudioManager: stopping listening…")
        self._is_running = False
        self._transition(AudioState.IDLE)

        self.microphone.stop()
        self.wake_detector.unload()

        # Unblock STT worker
        try:
            self._stt_queue.put_nowait(None)  # type: ignore[arg-type]
        except queue.Full:
            pass
        if self._stt_thread and self._stt_thread.is_alive():
            self._stt_thread.join(timeout=3.0)
        logger.info("AudioManager: stopped")

    def shutdown(self) -> None:
        """Complete shutdown of all audio systems including TTS and STT."""
        self.stop()
        try:
            self.tts.stop()
        except Exception:
            pass
        try:
            self.stt.unload()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Push-to-talk interface
    # ------------------------------------------------------------------

    def ptt_press(self) -> None:
        self.microphone.push_to_talk_press()
        self._transition(AudioState.LISTENING)

    def ptt_release(self) -> None:
        self.microphone.push_to_talk_release()

    # ------------------------------------------------------------------
    # TTS interface (pass-through)
    # ------------------------------------------------------------------

    def speak(self, text: str, priority: int = 0) -> int:
        """Queue text for speech. Transitions to SPEAKING state."""
        self._transition(AudioState.SPEAKING)
        return self.tts.speak(text, priority=priority)

    def speak_now(self, text: str) -> int:
        """Interrupt current speech and say text immediately."""
        self._transition(AudioState.SPEAKING)
        return self.tts.speak_now(text)

    def interrupt_speech(self) -> None:
        self.tts.interrupt()

    # ------------------------------------------------------------------
    # Manual transcription (for external audio)
    # ------------------------------------------------------------------

    def transcribe_audio(self, audio: np.ndarray, sample_rate: int = 16_000) -> TranscriptionResult:
        """Synchronously transcribe audio. Blocks until done."""
        self._transition(AudioState.PROCESSING)
        result = self.stt.transcribe(audio, sample_rate=sample_rate)
        self._transition(AudioState.LISTENING)
        return result

    # ------------------------------------------------------------------
    # Configuration updates
    # ------------------------------------------------------------------

    def set_sensitivity(self, sensitivity: float) -> None:
        self.wake_detector.set_sensitivity(sensitivity)
        self.config.microphone.vad_energy_threshold = max(0.001, sensitivity * 0.05)

    def set_tts_rate(self, rate: int) -> None:
        self.tts.set_rate(rate)

    def set_tts_volume(self, volume: float) -> None:
        self.tts.set_volume(volume)

    def set_wake_phrases(self, phrases: list[str]) -> None:
        self.wake_detector.set_wake_phrases(phrases)

    @property
    def state(self) -> AudioState:
        with self._state_lock:
            return self._state

    @property
    def current_audio_level(self) -> float:
        return self.microphone.current_level

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_audio_level(self, level: float) -> None:
        try:
            self.signals.audio_level_changed.emit(level)
        except Exception:
            pass

    def _on_vad_start(self) -> None:
        """Called when VAD detects the start of an utterance."""
        if self._state == AudioState.SPEAKING and self.config.mute_mic_while_speaking:
            return  # ignore own TTS echo
        logger.debug("VAD: speech start detected")

    def _on_vad_end(self, chunks: list[AudioChunk]) -> None:
        """Called when VAD detects end of utterance – queue for STT."""
        if self._state == AudioState.SPEAKING and self.config.mute_mic_while_speaking:
            logger.debug("Mic muted while TTS speaking – ignoring utterance")
            return
        if not self._is_running:
            return
        try:
            self._stt_queue.put_nowait(chunks)
        except queue.Full:
            logger.warning("STT queue full – dropping utterance")

    def _on_tts_state_change(self, tts_state: TTSState) -> None:
        try:
            self.signals.tts_state_changed.emit(tts_state.name)
        except Exception:
            pass

        if tts_state == TTSState.IDLE and self._state == AudioState.SPEAKING:
            # TTS finished → go back to LISTENING
            if self.config.auto_start_listening:
                self._transition(AudioState.LISTENING)

    def _on_wake_word(self, result: WakeWordResult) -> None:
        logger.info("Wake word: '%s' (%.2f)", result.phrase, result.confidence)
        try:
            self.signals.wake_word_detected.emit(result.phrase)
        except Exception:
            pass
        self._transition(AudioState.LISTENING)

    # ------------------------------------------------------------------
    # STT worker
    # ------------------------------------------------------------------

    def _stt_worker(self) -> None:
        """Background thread: takes utterance chunks, runs STT, fires callbacks."""
        logger.debug("STT worker started")
        while self._is_running:
            try:
                chunks = self._stt_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if chunks is None:
                break  # stop signal

            self._transition(AudioState.PROCESSING)

            # Assemble audio array
            arrays = [c.data.flatten() for c in chunks if c is not None]
            if not arrays:
                self._transition(AudioState.LISTENING)
                continue

            audio = np.concatenate(arrays).astype(np.float32)
            result = self.stt.transcribe(audio, sample_rate=self.config.microphone.sample_rate)

            raw_text = result.text.strip()
            logger.info("STT raw result: '%s' (confidence=%.2f)", raw_text, result.confidence)

            # Filter out empty, very low confidence (< 0.28), or Whisper noise hallucination bracket tokens
            if raw_text and result.confidence >= 0.28 and not (raw_text.startswith("[") and raw_text.endswith("]")):
                command_text = raw_text
                has_ww = self.wake_detector.check_text(raw_text) is not None
                if has_ww:
                    command_text = self.wake_detector.strip_wake_word(raw_text)

                if self.config.require_wake_word and not has_ww:
                    logger.info("Wake word required but not heard in: '%s'", raw_text)
                else:
                    logger.info("Transcribed speech ready: '%s' (conf=%.2f)", command_text, result.confidence)
                    if self.on_transcription:
                        try:
                            self.on_transcription(result)
                        except Exception:
                            pass
                    try:
                        self.signals.transcription_ready.emit(command_text, result.confidence)
                    except Exception:
                        pass
                    if self.on_command:
                        try:
                            self.on_command(command_text, result.confidence)
                        except Exception:
                            pass

            self._transition(AudioState.LISTENING)

        logger.debug("STT worker exited")

    def set_wake_word_enabled(self, enabled: bool) -> None:
        """Enable or disable requirement of wake word before commands."""
        self.config.require_wake_word = enabled
        logger.info("Wake word requirement set to: %s", enabled)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _transition(self, new_state: AudioState) -> None:
        with self._state_lock:
            if self._state == new_state:
                return
            old_state = self._state
            self._state = new_state

        logger.debug("State: %s → %s", old_state.name, new_state.name)
        try:
            self.signals.state_changed.emit(new_state.name)
        except Exception:
            pass
        if self.on_state_change:
            try:
                self.on_state_change(new_state)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "AudioManager":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    def on_command(text: str, confidence: float) -> None:
        print(f"\n🎤 COMMAND: '{text}' (confidence={confidence:.2f})")

    def on_state(state: AudioState) -> None:
        icons = {
            AudioState.IDLE: "⏸",
            AudioState.LISTENING: "🎙",
            AudioState.PROCESSING: "⚙",
            AudioState.SPEAKING: "🔊",
            AudioState.ERROR: "❌",
        }
        print(f"  State: {icons.get(state, '?')} {state.name}")

    cfg = AudioManagerConfig(
        stt=STTConfig(model_size="tiny"),
        require_wake_word=True,
    )
    am = AudioManager(config=cfg)
    am.on_command = on_command
    am.on_state_change = on_state

    with am:
        am.speak("JARVIS is online. Say hey Jarvis to wake me.")
        print("Listening… (Ctrl+C to quit)")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nShutting down…")
