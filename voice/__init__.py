"""
voice/__init__.py
-----------------
JARVIS Voice & Audio subsystem.
"""

from .microphone import Microphone, MicrophoneConfig, AudioChunk
from .speech_to_text import SpeechToText, STTConfig, TranscriptionResult
from .text_to_speech import TextToSpeech, TTSConfig, TTSState
from .wake_word import WakeWordDetector, WakeWordConfig, WakeWordResult
from .audio_manager import AudioManager, AudioManagerConfig, AudioState

__all__ = [
    "Microphone", "MicrophoneConfig", "AudioChunk",
    "SpeechToText", "STTConfig", "TranscriptionResult",
    "TextToSpeech", "TTSConfig", "TTSState",
    "WakeWordDetector", "WakeWordConfig", "WakeWordResult",
    "AudioManager", "AudioManagerConfig", "AudioState",
]
