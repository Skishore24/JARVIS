"""Tests for Memory and Database layer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from memory.database import init_db
from memory.memory_manager import MemoryManager


class TestMemory(unittest.TestCase):

    def setUp(self):
        init_db()
        self.mem = MemoryManager()

    def test_session_lifecycle(self):
        # 1. Create session
        sid = self.mem.new_session(title="Unit Test Session")
        self.assertIsNotNone(sid)
        self.assertIsInstance(sid, str)

        # 2. Add messages
        m1_id = self.mem.add_message(sid, "user", "Hello test user")
        m2_id = self.mem.add_message(sid, "assistant", "Hello test assistant")
        self.assertIsInstance(m1_id, int)
        self.assertIsInstance(m2_id, int)

        # 3. Retrieve messages
        recent = self.mem.get_recent_messages(sid)
        self.assertGreaterEqual(len(recent), 2)
        contents = [m.content for m in recent]
        self.assertIn("Hello test user", contents)
        self.assertIn("Hello test assistant", contents)

        # 4. List sessions
        sessions = self.mem.list_sessions(limit=5)
        self.assertGreaterEqual(len(sessions), 1)

        # 5. Delete message
        deleted = self.mem.delete_message(m1_id)
        self.assertTrue(deleted)


if __name__ == "__main__":
    unittest.main()
