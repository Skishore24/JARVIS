"""Tests for Windows Automation tools."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from automation.app_launcher import AppLauncher, APP_REGISTRY
from automation.system_control import SystemControl
from automation.browser_control import BrowserControl
from automation.file_manager import FileManager


class TestAutomation(unittest.TestCase):

    def setUp(self):
        self.launcher = AppLauncher()
        self.sys = SystemControl()
        self.browser = BrowserControl()
        self.files = FileManager()

    def test_app_registry(self):
        self.assertIn("notepad", APP_REGISTRY)
        self.assertIn("calculator", APP_REGISTRY)
        self.assertIn("chrome", APP_REGISTRY)
        self.assertIn("vscode", APP_REGISTRY)

    def test_system_info(self):
        res = self.sys.get_system_info()
        self.assertTrue(res.success)
        self.assertIn("cpu", res.data)
        self.assertIn("ram", res.data)

    def test_volume_query(self):
        vol = self.sys.get_volume()
        self.assertIsInstance(vol, int)
        self.assertGreaterEqual(vol, 0)
        self.assertLessEqual(vol, 100)

    def test_file_create_read_delete(self):
        test_path = str(Path(__file__).parent.parent / "data" / "unit_test_tmp.txt")
        # 1. Create
        create_res = self.files.create_file(test_path, "Automated Test Content")
        self.assertTrue(create_res.success)

        # 2. Read
        read_res = self.files.read_file(test_path)
        self.assertTrue(read_res.success)
        self.assertEqual(read_res.data.get("content"), "Automated Test Content")

        # 3. Clean up
        import os
        if os.path.exists(test_path):
            os.remove(test_path)


if __name__ == "__main__":
    unittest.main()
