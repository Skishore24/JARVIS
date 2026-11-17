"""
Tests for Voice Subsystems (Microphone VAD, Wake Word, TTS, Audio Manager)
"""

import unittest
import numpy as np
from voice.microphone import Microphone, MicrophoneConfig, AudioChunk
from voice.wake_word import WakeWordDetector, WakeWordConfig
from voice.text_to_speech import TextToSpeech, TTSConfig
from voice.audio_manager import AudioManager, AudioManagerConfig


class TestVoicePipeline(unittest.TestCase):

    def test_microphone_vad_detection(self):
        """Verify VAD triggers on speech energy and flushes after silence."""
        config = MicrophoneConfig(
            sample_rate=16000,
            block_duration_ms=30,
            vad_energy_threshold=0.002,
            vad_min_speech_ms=60,
            vad_silence_ms=90,
        )
        mic = Microphone(config)

        speech_started = []
        utterances_flushed = []

        mic.set_vad_start_callback(lambda: speech_started.append(True))
        mic.set_vad_end_callback(lambda chunks: utterances_flushed.append(chunks))

        # 1. Feed 4 blocks of silence (rms ~ 0.0001)
        silence = np.zeros(480, dtype=np.float32)
        for _ in range(4):
            mic._update_vad(AudioChunk(data=silence, sample_rate=16000, energy=0.0001), 0.0001)

        self.assertFalse(mic.is_voice_active)
        self.assertEqual(len(speech_started), 0)

        # 2. Feed 3 blocks of speech (rms ~ 0.01 > 0.002 threshold, total 90ms >= 60ms)
        speech = np.full(480, 0.01, dtype=np.float32)
        for _ in range(3):
            mic._update_vad(AudioChunk(data=speech, sample_rate=16000, energy=0.01), 0.01)

        self.assertTrue(mic.is_voice_active)
        self.assertGreaterEqual(len(speech_started), 1)

        # 3. Feed 4 blocks of silence (total 120ms >= 90ms vad_silence_ms)
        for _ in range(4):
            mic._update_vad(AudioChunk(data=silence, sample_rate=16000, energy=0.0001), 0.0001)

        self.assertFalse(mic.is_voice_active)
        self.assertEqual(len(utterances_flushed), 1)
        self.assertGreater(len(utterances_flushed[0]), 0)

    def test_wake_word_strip_and_check(self):
        """Test wake phrase detection and prefix stripping."""
        detector = WakeWordDetector(WakeWordConfig(wake_phrases=["hey jarvis", "jarvis"]))
        
        # Test detection
        res = detector.check_text("Hey Jarvis, what is the weather today?")
        self.assertIsNotNone(res)
        
        # Test stripping
        cleaned = detector.strip_wake_word("Hey Jarvis, what is the weather today?")
        self.assertEqual(cleaned.lower(), "what is the weather today?")

        cleaned_direct = detector.strip_wake_word("Jarvis open chrome")
        self.assertEqual(cleaned_direct.lower(), "open chrome")

    def test_tts_voice_enumeration(self):
        """Test SAPI voice enumeration returns valid voice dicts."""
        voices = TextToSpeech.list_voices()
        self.assertIsInstance(voices, list)
        if voices:
            self.assertIn("name", voices[0])
            self.assertIn("id", voices[0])

    def test_clean_speech_formatting(self):
        """Verify markdown, links, code blocks, and JSON are cleanly stripped for TTS."""
        from ui.main_window import MainWindow
        raw = 'Sure! Here is the code: ```python\nprint("hello")\n```. Check [Google](https://google.com) and `test_var`.'
        cleaned = MainWindow._clean_for_speech(raw)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertIn("Sure", cleaned)
        self.assertIn("Google", cleaned)


if __name__ == "__main__":
    unittest.main()
