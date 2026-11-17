"""Tests for Security, Task Planning, and UI components."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import unittest
from core.permission_manager import PermissionManager, PermissionSet
from core.task_planner import TaskPlan, TaskStep
from core.execution_engine import ExecutionEngine
from core.command_router import CommandRouter
from services.system_monitor import SystemMonitor
from services.notification_service import NotificationService


class TestSecurityAndPlanner(unittest.TestCase):

    def setUp(self):
        self.pm = PermissionManager()
        self.monitor = SystemMonitor()
        self.notifier = NotificationService()
        self.router = CommandRouter(self.pm, self.monitor, self.notifier)

    def test_permission_checks(self):
        # Chat always allowed
        self.assertTrue(self.pm.is_allowed("CHAT"))
        # File operations allowed by default
        self.assertTrue(self.pm.is_allowed("FILE_OPERATION"))

        # Explicit deny override
        self.pm.deny("FILE_OPERATION")
        self.assertFalse(self.pm.is_allowed("FILE_OPERATION"))

        # Reset allow
        self.pm.allow("FILE_OPERATION")
        self.assertTrue(self.pm.is_allowed("FILE_OPERATION"))

    def test_command_router_dispatch(self):
        # System monitor tool dispatch
        res = self.router.dispatch("SYSTEM_MONITOR", {"metric": "ram"})
        self.assertIn("RAM", res)

        # Chat intent dispatch
        chat_res = self.router.dispatch("CHAT", {})
        self.assertIsInstance(chat_res, str)

    def test_task_plan_execution(self):
        plan = TaskPlan(
            goal="Test System Metric Gathering",
            steps=[
                TaskStep(
                    step_id=1,
                    description="Get RAM info",
                    intent="SYSTEM_MONITOR",
                    params={"metric": "ram"},
                )
            ]
        )
        self.assertEqual(len(plan), 1)
        next_step = plan.next_pending()
        self.assertIsNotNone(next_step)
        self.assertEqual(next_step.step_id, 1)

        executor = ExecutionEngine(self.router)
        summary = executor.execute(plan)
        self.assertIsInstance(summary, str)
        self.assertTrue(plan.completed)


class TestUIOffscreen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_main_window_creation(self):
        from ui.main_window import MainWindow
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertGreaterEqual(win.width(), 1200)
        self.assertGreaterEqual(win.height(), 780)

    def test_dashboard_metrics(self):
        from ui.dashboard import DashboardPage
        page = DashboardPage()
        page.set_cpu(45.5)
        page.set_ram(62.0)
        page.set_state("THINKING")
        self.assertEqual(page._state_lbl.text(), "THINKING")

    def test_chat_page_messages(self):
        from ui.chat_page import ChatPage
        chat = ChatPage()
        chat.add_user_message("Hello from test")
        chat.add_ai_message("Hello response")
        self.assertGreater(chat._messages_layout.count(), 1)


if __name__ == "__main__":
    unittest.main()
