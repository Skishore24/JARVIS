"""
voice/microphone.py
-------------------
SoundDevice-based microphone capture with VAD, push-to-talk, and thread-safe buffering.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available – microphone capture disabled")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class AudioChunk:
    """Single chunk of audio data captured from the microphone."""
    data: np.ndarray          # shape (frames, channels) or (frames,)
    sample_rate: int
    timestamp: float = field(default_factory=time.monotonic)
    energy: float = 0.0       # RMS energy level, 0-1


@dataclass
class MicrophoneConfig:
    """Configuration for the microphone capture."""
    sample_rate: int = 16_000          # Hz – Whisper expects 16 kHz
    channels: int = 1                  # mono
    dtype: str = "float32"
    block_duration_ms: int = 30        # ms per callback chunk
    device: Optional[int] = None       # None = system default
    vad_energy_threshold: float = 0.002 # RMS threshold for voice activity (sensitive to natural room voice)
    vad_min_speech_ms: int = 150       # min consecutive ms to trigger VAD
    vad_silence_ms: int = 850          # ms of silence to end utterance (allows natural pauses between words)
    buffer_duration_s: int = 30        # ring buffer size in seconds
    push_to_talk_key: Optional[str] = None  # reserved for hotkey integration


# ---------------------------------------------------------------------------
# Main microphone class
# ---------------------------------------------------------------------------

class Microphone:
    """
    Captures audio from the system microphone using sounddevice.

    Features
    --------
    - Thread-safe ring buffer (deque)
    - Real-time RMS energy level
    - Voice Activity Detection (VAD) based on energy
    - Push-to-talk support via PTT flag
    - Microphone device enumeration and selection
    - Graceful error handling
    """

    def __init__(self, config: Optional[MicrophoneConfig] = None) -> None:
        self.config = config or MicrophoneConfig()
        self._lock = threading.Lock()

        # Ring buffer: stores AudioChunk objects
        max_chunks = int(
            self.config.buffer_duration_s * 1000 / self.config.block_duration_ms
        )
        self._buffer: deque[AudioChunk] = deque(maxlen=max_chunks)

        # State
        self._stream: Optional["sd.InputStream"] = None
        self._is_running = False
        self._current_level: float = 0.0  # 0-1 RMS
        self._ptt_active = False

        # VAD state
        self._vad_speech_ms_accum: float = 0.0
        self._vad_silence_ms_accum: float = 0.0
        self._vad_onset_silence_ms: float = 0.0
        self._ambient_noise: float = 0.0005
        self._is_voice_active = False

        # Callbacks
        self._on_level_change: Optional[Callable[[float], None]] = None
        self._on_vad_start: Optional[Callable[[], None]] = None
        self._on_vad_end: Optional[Callable[[list[AudioChunk]], None]] = None
        self._utterance_buffer: list[AudioChunk] = []

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> list[dict]:
        """Return a list of available input devices."""
        if not SOUNDDEVICE_AVAILABLE:
            return []
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_sample_rate": dev["default_samplerate"],
                    "is_default": i == sd.default.device[0],
                })
        return devices

    @staticmethod
    def get_default_device() -> Optional[dict]:
        """Return the default input device info, or None."""
        if not SOUNDDEVICE_AVAILABLE:
            return None
        try:
            idx = sd.default.device[0]
            dev = sd.query_devices(idx)
            return {"index": idx, "name": dev["name"]}
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Callbacks / event hooks
    # ------------------------------------------------------------------

    def set_level_callback(self, cb: Callable[[float], None]) -> None:
        """Called with RMS energy (0-1) on every audio block."""
        self._on_level_change = cb

    def set_vad_start_callback(self, cb: Callable[[], None]) -> None:
        """Called when voice activity is detected (utterance start)."""
        self._on_vad_start = cb

    def set_vad_end_callback(self, cb: Callable[[list[AudioChunk]], None]) -> None:
        """Called with the list of chunks in the utterance when silence detected."""
        self._on_vad_end = cb

    # ------------------------------------------------------------------
    # Push-to-talk
    # ------------------------------------------------------------------

    def push_to_talk_press(self) -> None:
        """Signal that the PTT key/button is held down."""
        self._ptt_active = True
        logger.debug("PTT pressed")

    def push_to_talk_release(self) -> None:
        """Signal that the PTT key/button was released – flush utterance."""
        self._ptt_active = False
        logger.debug("PTT released")
        self._flush_utterance()

    # ------------------------------------------------------------------
    # Buffer access
    # ------------------------------------------------------------------

    def get_audio_numpy(self, duration_s: Optional[float] = None) -> np.ndarray:
        """
        Return buffered audio as a 1-D float32 numpy array.

        Parameters
        ----------
        duration_s:
            If given, return only the last N seconds. If None, return all.
        """
        with self._lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            chunks = list(self._buffer)

        if duration_s is not None:
            # Trim to the requested duration
            needed_ms = duration_s * 1000
            selected = []
            total_ms = 0.0
            for chunk in reversed(chunks):
                chunk_ms = len(chunk.data) / self.config.sample_rate * 1000
                selected.insert(0, chunk)
                total_ms += chunk_ms
                if total_ms >= needed_ms:
                    break
            chunks = selected

        arrays = [c.data.flatten() for c in chunks]
        return np.concatenate(arrays).astype(np.float32) if arrays else np.zeros(0, dtype=np.float32)

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    @property
    def current_level(self) -> float:
        return self._current_level

    @property
    def is_voice_active(self) -> bool:
        return self._is_voice_active

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """
        Start microphone capture. Returns True on success.
        """
        if not SOUNDDEVICE_AVAILABLE:
            logger.error("sounddevice not installed – cannot start microphone")
            return False
        if self._is_running:
            logger.warning("Microphone already running")
            return True

        try:
            blocksize = int(
                self.config.sample_rate * self.config.block_duration_ms / 1000
            )
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=blocksize,
                device=self.config.device,
                callback=self._audio_callback,
                latency="low",
            )
            self._stream.start()
            self._is_running = True
            logger.info(
                "Microphone started: %d Hz, %d ch, device=%s",
                self.config.sample_rate,
                self.config.channels,
                self.config.device or "default",
            )
            return True
        except sd.PortAudioError as exc:
            if "Invalid device" in str(exc):
                logger.error("Invalid microphone device index: %s", self.config.device)
            elif "Permission" in str(exc) or "Access" in str(exc):
                logger.error("Microphone permission denied: %s", exc)
            else:
                logger.error("PortAudio error starting microphone: %s", exc)
            return False
        except Exception as exc:
            logger.error("Failed to start microphone: %s", exc)
            return False

    def stop(self) -> None:
        """Stop microphone capture."""
        if not self._is_running:
            return
        self._is_running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.debug("Error closing stream: %s", exc)
            self._stream = None
        logger.info("Microphone stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """sounddevice callback – runs in a separate OS thread."""
        if status:
            logger.debug("sounddevice status: %s", status)

        audio = indata.copy()
        rms = float(np.sqrt(np.mean(audio ** 2)))
        self._current_level = min(rms * 25.0, 1.0)  # scale visually 0-1

        chunk = AudioChunk(
            data=audio,
            sample_rate=self.config.sample_rate,
            energy=rms,
        )

        with self._lock:
            self._buffer.append(chunk)

        if self._on_level_change:
            try:
                self._on_level_change(self._current_level)
            except Exception:
                pass

        self._update_vad(chunk, rms)

    def _update_vad(self, chunk: AudioChunk, rms: float) -> None:
        """Energy-based Voice Activity Detection with ambient tracking and pre-roll."""
        block_ms = self.config.block_duration_ms

        if self._ptt_active:
            # PTT mode: always treat as speech
            self._utterance_buffer.append(chunk)
            if not self._is_voice_active:
                self._is_voice_active = True
                if self._on_vad_start:
                    try:
                        self._on_vad_start()
                    except Exception:
                        pass
            return

        # Adaptively track ambient noise when quiet
        if not self._is_voice_active and rms < self.config.vad_energy_threshold * 2.0:
            self._ambient_noise = 0.96 * self._ambient_noise + 0.04 * rms

        effective_threshold = max(self.config.vad_energy_threshold, self._ambient_noise * 1.8)
        is_speech = rms >= effective_threshold

        if is_speech:
            self._vad_speech_ms_accum += block_ms
            self._vad_onset_silence_ms = 0.0
            self._utterance_buffer.append(chunk)

            if not self._is_voice_active and self._vad_speech_ms_accum >= self.config.vad_min_speech_ms:
                self._is_voice_active = True
                logger.info("VAD: speech started (rms=%.4f, threshold=%.4f)", rms, effective_threshold)
                if self._on_vad_start:
                    try:
                        self._on_vad_start()
                    except Exception:
                        pass
        else:
            if not self._is_voice_active:
                # Brief pause before speech onset is confirmed: grace period
                self._vad_onset_silence_ms += block_ms
                if self._vad_onset_silence_ms > 120:
                    self._vad_speech_ms_accum = 0.0
                    self._utterance_buffer = self._utterance_buffer[-8:]  # keep ~240ms pre-roll
                else:
                    self._utterance_buffer.append(chunk)
            else:
                self._vad_silence_ms_accum += block_ms
                self._utterance_buffer.append(chunk)  # keep trailing silence
                if self._vad_silence_ms_accum >= self.config.vad_silence_ms:
                    self._flush_utterance()

    def _flush_utterance(self) -> None:
        """End the current utterance and fire the VAD-end callback."""
        if not self._utterance_buffer:
            return
        utterance = list(self._utterance_buffer)
        self._utterance_buffer.clear()
        self._is_voice_active = False
        self._vad_silence_ms_accum = 0.0
        self._vad_speech_ms_accum = 0.0
        self._vad_onset_silence_ms = 0.0
        logger.info("VAD: utterance ended (%d chunks, approx %.2fs)", len(utterance), len(utterance) * self.config.block_duration_ms / 1000)
        if self._on_vad_end:
            try:
                self._on_vad_end(utterance)
            except Exception as exc:
                logger.error("VAD-end callback error: %s", exc)

    def __enter__(self) -> "Microphone":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Available devices:")
    for d in Microphone.list_devices():
        print(f"  [{d['index']}] {d['name']} (default={d['is_default']})")

    mic = Microphone()
    mic.set_level_callback(lambda lvl: print(f"\rLevel: {'█' * int(lvl * 40):<40}", end=""))
    mic.set_vad_start_callback(lambda: print("\n[VAD] Speech started"))
    mic.set_vad_end_callback(lambda chunks: print(f"\n[VAD] Utterance: {len(chunks)} chunks"))

    with mic:
        print("Recording for 10 seconds…")
        time.sleep(10)
    print("Done.")
