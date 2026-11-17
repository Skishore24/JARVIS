"""
voice/wake_word.py
------------------
Wake-word detection for JARVIS.

Strategy (in priority order):
1. openwakeword  – neural keyword spotting (best accuracy, needs model download)
2. Text-match    – match after STT transcription (most reliable fallback)

Both strategies share the same WakeWordDetector API.
"""

from __future__ import annotations

import logging
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Optional dependency
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OPENWAKEWORD_AVAILABLE = True
except Exception:
    OPENWAKEWORD_AVAILABLE = False
    logger.info("openwakeword not available – using text-match fallback")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class WakeWordConfig:
    wake_phrases: list[str] = field(default_factory=lambda: [
        "hey jarvis",
        "jarvis",
        "ok jarvis",
        "okay jarvis",
    ])
    sensitivity: float = 0.5           # 0-1; higher = more sensitive (more false positives)
    oww_model_name: str = "hey_jarvis" # openwakeword model identifier
    oww_inference_rate_ms: int = 80    # ms between OWW inference calls
    sample_rate: int = 16_000          # must match microphone
    chunk_duration_ms: int = 80        # audio chunk size for OWW
    cooldown_s: float = 2.0           # seconds before next wake can trigger
    use_openwakeword: bool = True      # try OWW first; set False to force text-match


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------

@dataclass
class WakeWordResult:
    detected: bool
    phrase: str = ""
    confidence: float = 0.0
    method: str = ""    # "openwakeword" or "text_match"
    timestamp: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class WakeWordDetector:
    """
    Detects the wake word in audio or in transcribed text.

    Two operating modes
    -------------------
    1. Stream mode (audio):
       Feed chunks via process_audio_chunk() — OWW runs inference.
    2. Text mode (post-STT):
       Call check_text(transcribed) — simple phrase matching.

    Callbacks
    ---------
    Set on_wake_word to be notified when the wake word is heard.
    """

    def __init__(self, config: Optional[WakeWordConfig] = None) -> None:
        self.config = config or WakeWordConfig()
        self._model: Optional[OWWModel] = None
        self._loaded = False
        self._last_trigger_time: float = 0.0
        self._lock = threading.Lock()
        self.on_wake_word: Optional[Callable[[WakeWordResult], None]] = None

        # Pre-compile regex patterns for text matching
        self._patterns: list[re.Pattern] = []
        self._compile_patterns()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _compile_patterns(self) -> None:
        """Build case-insensitive regex patterns from wake phrases."""
        self._patterns = []
        for phrase in self.config.wake_phrases:
            # Allow optional punctuation and extra words around the phrase
            escaped = re.escape(phrase.lower())
            # Also create a "words only" pattern to catch variations
            self._patterns.append(
                re.compile(r"\b" + escaped.replace(r"\ ", r"[\s,\.]+") + r"\b", re.IGNORECASE)
            )

    def load(self) -> bool:
        """
        Attempt to load openwakeword model.
        Returns True if OWW is available, False if falling back to text-match.
        """
        if not self.config.use_openwakeword or not OPENWAKEWORD_AVAILABLE:
            logger.info("Wake word: using text-match mode")
            return False

        try:
            logger.info("Loading openwakeword model '%s'…", self.config.oww_model_name)
            # openwakeword downloads models on first use
            self._model = OWWModel(
                wakeword_models=[self.config.oww_model_name],
                inference_framework="onnx",
            )
            self._loaded = True
            logger.info("openwakeword model loaded")
            return True
        except Exception as exc:
            logger.warning("openwakeword load failed (%s) – falling back to text-match", exc)
            self._model = None
            self._loaded = False
            return False

    def unload(self) -> None:
        self._model = None
        self._loaded = False

    @property
    def is_using_oww(self) -> bool:
        return self._loaded and self._model is not None

    # ------------------------------------------------------------------
    # Audio stream mode (openwakeword)
    # ------------------------------------------------------------------

    def process_audio_chunk(self, audio_chunk: np.ndarray) -> Optional[WakeWordResult]:
        """
        Feed a raw audio chunk (float32 at 16 kHz) to the OWW model.
        Returns a WakeWordResult if wake word detected, else None.
        Only usable when OWW model is loaded.
        """
        if not self._loaded or self._model is None:
            return None

        # OWW expects int16
        audio_int16 = (audio_chunk * 32767).astype(np.int16)

        try:
            prediction = self._model.predict(audio_int16)
        except Exception as exc:
            logger.debug("OWW predict error: %s", exc)
            return None

        # Find max confidence across all wake word models
        best_model = None
        best_score = 0.0
        for model_name, score in prediction.items():
            if isinstance(score, (list, np.ndarray)):
                s = float(np.max(score))
            else:
                s = float(score)
            if s > best_score:
                best_score = s
                best_model = model_name

        threshold = self.config.sensitivity * 0.8  # map 0-1 sensitivity to 0-0.8 OWW score
        if best_score >= threshold:
            return self._trigger(best_model or "wake", best_score, "openwakeword")
        return None

    # ------------------------------------------------------------------
    # Text match mode (post-STT)
    # ------------------------------------------------------------------

    def check_text(self, text: str) -> Optional[WakeWordResult]:
        """
        Check if transcribed text contains a wake phrase.
        Returns WakeWordResult if matched, else None.
        """
        if not text:
            return None

        lower = text.lower().strip()
        for phrase, pattern in zip(self.config.wake_phrases, self._patterns):
            if pattern.search(lower):
                return self._trigger(phrase, 1.0, "text_match")

        # Fuzzy: check if any single phrase word is present (low-confidence)
        # Only for short transcriptions that might just be the wake word
        words = lower.split()
        if len(words) <= 3:
            for phrase in self.config.wake_phrases:
                phrase_words = phrase.lower().split()
                overlap = sum(1 for w in phrase_words if w in words)
                ratio = overlap / max(len(phrase_words), 1)
                if ratio >= 0.8:
                    score = ratio * self.config.sensitivity
                    return self._trigger(phrase, score, "text_match_fuzzy")

        return None

    def strip_wake_word(self, text: str) -> str:
        """Remove the wake phrase from transcribed text to get the actual command."""
        lower = text.lower()
        for phrase in sorted(self.config.wake_phrases, key=len, reverse=True):
            # Try to remove the phrase + optional trailing punctuation/spaces
            escaped = re.escape(phrase)
            cleaned = re.sub(
                r"^[\s,\.]*" + escaped + r"[\s,\.]*",
                "",
                lower,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned != lower:
                # Restore capitalisation of remainder from original
                start = text.lower().find(cleaned)
                if start >= 0:
                    return text[start:].strip()
                return cleaned
        return text

    # ------------------------------------------------------------------
    # Configuration updates
    # ------------------------------------------------------------------

    def set_sensitivity(self, sensitivity: float) -> None:
        self.config.sensitivity = max(0.0, min(1.0, sensitivity))

    def add_wake_phrase(self, phrase: str) -> None:
        phrase = phrase.lower().strip()
        if phrase not in self.config.wake_phrases:
            self.config.wake_phrases.append(phrase)
            self._compile_patterns()

    def set_wake_phrases(self, phrases: list[str]) -> None:
        self.config.wake_phrases = [p.lower().strip() for p in phrases]
        self._compile_patterns()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trigger(self, phrase: str, confidence: float, method: str) -> Optional[WakeWordResult]:
        """Create a trigger result, respecting cooldown."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_trigger_time < self.config.cooldown_s:
                return None
            self._last_trigger_time = now

        result = WakeWordResult(
            detected=True,
            phrase=phrase,
            confidence=confidence,
            method=method,
        )
        logger.info("Wake word detected: '%s' (%.2f) via %s", phrase, confidence, method)
        if self.on_wake_word:
            try:
                self.on_wake_word(result)
            except Exception as exc:
                logger.error("Wake word callback error: %s", exc)
        return result

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "WakeWordDetector":
        self.load()
        return self

    def __exit__(self, *_) -> None:
        self.unload()


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    detector = WakeWordDetector()
    detector.load()

    test_phrases = [
        "hey jarvis what time is it",
        "turn on the lights",
        "jarvis, play some music",
        "hello there",
        "okay jarvis, remind me at 5pm",
    ]
    for phrase in test_phrases:
        result = detector.check_text(phrase)
        if result:
            command = detector.strip_wake_word(phrase)
            print(f"WAKE: '{phrase}' → command='{command}' | conf={result.confidence:.2f}")
        else:
            print(f"SKIP: '{phrase}'")
