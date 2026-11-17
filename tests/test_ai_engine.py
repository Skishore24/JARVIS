"""Tests for AI Engine and Ollama integration."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from core.ai_engine import AIEngine


class TestAIEngine(unittest.TestCase):

    def setUp(self):
        self.ai = AIEngine()

    def test_health_check(self):
        healthy = self.ai.health_check()
        self.assertTrue(healthy, "Ollama service should be reachable")

    def test_list_models(self):
        models = self.ai.list_local_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0, "At least one model should be available")

    def test_is_model_available(self):
        available = self.ai.is_model_available("llama3.2:3b")
        self.assertTrue(available, "Default model llama3.2:3b should be available")

    def test_extract_intent_json(self):
        sample = '{"intent": "SYSTEM_MONITOR", "params": {"metric": "cpu"}}'
        intent = self.ai.extract_intent(sample)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.get("intent"), "SYSTEM_MONITOR")
        self.assertEqual(intent.get("params", {}).get("metric"), "cpu")

    def test_extract_intent_with_surrounding_text(self):
        sample = 'I will check your CPU now.\n{"intent": "SYSTEM_MONITOR", "params": {}}\nDone.'
        intent = self.ai.extract_intent(sample)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.get("intent"), "SYSTEM_MONITOR")

    def test_extract_intent_plain_chat(self):
        sample = "Hello! How can I help you today?"
        intent = self.ai.extract_intent(sample)
        self.assertIsNone(intent)


if __name__ == "__main__":
    unittest.main()
