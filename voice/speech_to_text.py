"""
voice/speech_to_text.py
-----------------------
Whisper-based speech-to-text using faster-whisper.
Supports GPU (CUDA / RTX 3050) with automatic CPU fallback.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available – STT will use fallback")

try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except Exception:
    CUDA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TranscriptionResult:
    text: str
    confidence: float          # 0-1 average segment probability
    language: str
    duration_s: float          # audio duration that was transcribed
    processing_time_s: float   # wall time for inference
    segments: list[dict] = field(default_factory=list)
    success: bool = True
    error: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class STTConfig:
    model_size: str = "base"           # "tiny", "base", "small", "medium", "large-v3"
    device: str = "auto"               # "auto", "cuda", "cpu"
    compute_type: str = "auto"         # "auto", "float16", "int8", "float32"
    language: Optional[str] = "en"     # None = auto-detect
    beam_size: int = 5
    best_of: int = 5
    temperature: float = 0.0
    vad_filter: bool = True            # built-in whisper VAD
    vad_min_silence_ms: int = 500
    min_audio_duration_s: float = 0.3  # ignore very short clips
    max_audio_duration_s: float = 60.0
    num_workers: int = 1               # CPU threads for model inference
    download_root: Optional[str] = None  # cache directory for model files


# ---------------------------------------------------------------------------
# STT Engine
# ---------------------------------------------------------------------------

class SpeechToText:
    """
    Transcribes audio (numpy float32 array at 16 kHz) to text using
    faster-whisper.

    Usage
    -----
    >>> stt = SpeechToText()
    >>> stt.load()
    >>> result = stt.transcribe(audio_array)
    >>> print(result.text)
    """

    def __init__(self, config: Optional[STTConfig] = None) -> None:
        self.config = config or STTConfig()
        self._model: Optional["WhisperModel"] = None
        self._model_lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._loaded = False
        self._device_used: str = "cpu"
        self._compute_type_used: str = "float32"

    # ------------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------------

    def _resolve_device(self) -> tuple[str, str]:
        """Return (device, compute_type) based on config and availability."""
        cfg_device = self.config.device.lower()
        cfg_compute = self.config.compute_type.lower()

        if cfg_device == "auto":
            device = "cuda" if CUDA_AVAILABLE else "cpu"
        else:
            device = cfg_device

        if device == "cuda" and not CUDA_AVAILABLE:
            logger.warning("CUDA requested but not available – falling back to CPU")
            device = "cpu"

        if cfg_compute == "auto":
            if device == "cuda":
                compute_type = "float16"   # optimal for RTX 3050 6 GB
            else:
                compute_type = "int8"      # fastest CPU quantization
        else:
            compute_type = cfg_compute

        return device, compute_type

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """
        Download (if necessary) and load the Whisper model.
        Thread-safe; subsequent calls are no-ops.
        Returns True on success.
        """
        if not FASTER_WHISPER_AVAILABLE:
            logger.error("faster-whisper is not installed")
            return False

        with self._load_lock:
            if self._loaded:
                return True

            device, compute_type = self._resolve_device()
            self._device_used = device
            self._compute_type_used = compute_type

            logger.info(
                "Loading Whisper '%s' on %s (%s)…",
                self.config.model_size, device, compute_type,
            )
            t0 = time.monotonic()
            try:
                kwargs = dict(
                    device=device,
                    compute_type=compute_type,
                    num_workers=self.config.num_workers,
                )
                if self.config.download_root:
                    kwargs["download_root"] = self.config.download_root

                self._model = WhisperModel(self.config.model_size, **kwargs)
                self._loaded = True
                elapsed = time.monotonic() - t0
                logger.info("Whisper model loaded in %.1f s", elapsed)
                return True
            except Exception as exc:
                logger.error("Failed to load Whisper model: %s", exc)
                # Retry on CPU if CUDA failed
                if device == "cuda":
                    logger.info("Retrying on CPU…")
                    try:
                        self._model = WhisperModel(
                            self.config.model_size,
                            device="cpu",
                            compute_type="int8",
                            num_workers=self.config.num_workers,
                        )
                        self._device_used = "cpu"
                        self._compute_type_used = "int8"
                        self._loaded = True
                        logger.info("Whisper loaded on CPU (fallback)")
                        return True
                    except Exception as exc2:
                        logger.error("CPU fallback also failed: %s", exc2)
                return False

    def unload(self) -> None:
        """Release the model from memory."""
        with self._load_lock:
            self._model = None
            self._loaded = False
            logger.info("Whisper model unloaded")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> str:
        return self._device_used

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16_000,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe a numpy audio array to text.

        Parameters
        ----------
        audio:
            1-D float32 array, ideally at 16 kHz.
        sample_rate:
            Sample rate of the audio. Resamples if != 16000.
        language:
            Override config language (None = auto-detect).

        Returns
        -------
        TranscriptionResult
        """
        t0 = time.monotonic()

        if not self._loaded:
            if not self.load():
                return TranscriptionResult(
                    text="", confidence=0.0, language="",
                    duration_s=0.0, processing_time_s=0.0,
                    success=False, error="Model not loaded",
                )

        # --- Validate / preprocess audio ---
        if audio is None or len(audio) == 0:
            return TranscriptionResult(
                text="", confidence=0.0, language="",
                duration_s=0.0, processing_time_s=time.monotonic() - t0,
                success=False, error="Empty audio",
            )

        audio = audio.flatten().astype(np.float32)

        # Resample if needed (simple linear interp – for heavy use add librosa)
        if sample_rate != 16_000:
            factor = 16_000 / sample_rate
            new_len = int(len(audio) * factor)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, new_len),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        duration_s = len(audio) / 16_000

        if duration_s < self.config.min_audio_duration_s:
            return TranscriptionResult(
                text="", confidence=0.0, language="en",
                duration_s=duration_s, processing_time_s=time.monotonic() - t0,
                success=True, error="Audio too short",
            )

        if duration_s > self.config.max_audio_duration_s:
            audio = audio[: int(self.config.max_audio_duration_s * 16_000)]
            duration_s = self.config.max_audio_duration_s

        # Normalize to prevent clipping
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.95

        # --- Inference ---
        lang = language or self.config.language
        try:
            with self._model_lock:
                segments_gen, info = self._model.transcribe(
                    audio,
                    language=lang,
                    beam_size=self.config.beam_size,
                    best_of=self.config.best_of,
                    temperature=self.config.temperature,
                    vad_filter=self.config.vad_filter,
                    vad_parameters={
                        "min_silence_duration_ms": self.config.vad_min_silence_ms,
                    } if self.config.vad_filter else None,
                )
                segments = list(segments_gen)

            # --- Aggregate results ---
            texts: list[str] = []
            probs: list[float] = []
            seg_dicts: list[dict] = []

            for seg in segments:
                texts.append(seg.text.strip())
                # avg_logprob is in log space; convert to probability
                prob = float(np.exp(max(seg.avg_logprob, -10)))
                probs.append(prob)
                seg_dicts.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                    "confidence": prob,
                    "no_speech_prob": seg.no_speech_prob,
                })

            full_text = " ".join(t for t in texts if t).strip()
            confidence = float(np.mean(probs)) if probs else 0.0

            processing_time = time.monotonic() - t0
            logger.debug(
                "STT: '%s' | conf=%.2f | lang=%s | %.2fs audio / %.2fs inference",
                full_text[:60], confidence, info.language, duration_s, processing_time,
            )

            return TranscriptionResult(
                text=full_text,
                confidence=confidence,
                language=info.language,
                duration_s=duration_s,
                processing_time_s=processing_time,
                segments=seg_dicts,
            )

        except Exception as exc:
            logger.error("Transcription error: %s", exc, exc_info=True)
            return TranscriptionResult(
                text="", confidence=0.0, language="",
                duration_s=duration_s, processing_time_s=time.monotonic() - t0,
                success=False, error=str(exc),
            )

    def transcribe_file(self, path: str) -> TranscriptionResult:
        """Convenience wrapper to transcribe a WAV/MP3/FLAC file."""
        try:
            import soundfile as sf
            audio, sr = sf.read(path, dtype="float32", always_2d=False)
            return self.transcribe(audio, sample_rate=sr)
        except ImportError:
            logger.error("soundfile not installed – cannot read audio files")
            return TranscriptionResult(
                text="", confidence=0.0, language="",
                duration_s=0.0, processing_time_s=0.0,
                success=False, error="soundfile not installed",
            )
        except Exception as exc:
            return TranscriptionResult(
                text="", confidence=0.0, language="",
                duration_s=0.0, processing_time_s=0.0,
                success=False, error=str(exc),
            )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "SpeechToText":
        self.load()
        return self

    def __exit__(self, *_) -> None:
        self.unload()


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    stt = SpeechToText(STTConfig(model_size="tiny"))
    with stt:
        print(f"Device: {stt.device}")
        # Synthesize a short silent clip to exercise the pipeline
        silence = np.zeros(16_000, dtype=np.float32)  # 1 s silence
        result = stt.transcribe(silence)
        print(f"Result: '{result.text}' | confidence={result.confidence:.2f}")
