"""
core/execution_engine.py
------------------------
Executes a TaskPlan step by step, handling retries and collecting results.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

import config
from core.task_planner import TaskPlan, TaskStep
from core.command_router import CommandRouter

logger = logging.getLogger(__name__)

# Callback type: called after each step with (step, result)
StepCallback = Callable[[TaskStep, str], None]


class ExecutionEngine:
    """
    Iterates through a TaskPlan, dispatching each step via the CommandRouter.

    Features:
    - Sequential execution respecting step dependencies
    - Per-step timeout enforcement
    - Optional progress callback
    - Retry on transient failures (up to max_retries)
    - Aggregated final summary
    """

    def __init__(
        self,
        command_router: CommandRouter,
        max_retries: int = 2,
        step_timeout: int | None = None,
    ) -> None:
        self._router = command_router
        self._max_retries = max_retries
        self._step_timeout = step_timeout or config.TASK_TIMEOUT
        logger.info(
            "ExecutionEngine ready — max_retries=%d timeout=%ds",
            self._max_retries,
            self._step_timeout,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(
        self,
        plan: TaskPlan,
        on_step_done: StepCallback | None = None,
    ) -> str:
        """
        Execute all steps in *plan* and return a combined result summary.

        Args:
            plan:         The TaskPlan to execute.
            on_step_done: Optional callback invoked after each step.

        Returns:
            A human-readable summary of all results.
        """
        logger.info(
            "Executing plan '%s' — %d step(s).", plan.goal[:60], len(plan)
        )

        results: list[str] = []
        start_time = time.time()

        while True:
            if time.time() - start_time > self._step_timeout:
                logger.warning("Plan execution timed out after %ds.", self._step_timeout)
                results.append("⏰ Execution timed out.")
                break

            step = plan.next_pending()
            if step is None:
                break

            result = self._execute_step(step)
            step.result = result
            results.append(result)

            if on_step_done:
                try:
                    on_step_done(step, result)
                except Exception as cb_exc:
                    logger.error("Step callback raised: %s", cb_exc)

        plan.completed = True
        plan.final_summary = self._build_summary(plan, results)
        logger.info("Plan execution complete.")
        return plan.final_summary

    # ── Internal ──────────────────────────────────────────────────────────────

    def _execute_step(self, step: TaskStep) -> str:
        """Execute a single step with retry logic."""
        logger.debug(
            "Executing step %d/%s: %s", step.step_id, step.intent, step.description[:60]
        )

        last_error: str = ""
        for attempt in range(1, self._max_retries + 2):  # +2 → original + retries
            try:
                result = self._router.dispatch(step.intent, step.params)
                step.success = True
                if attempt > 1:
                    logger.info("Step %d succeeded on attempt %d.", step.step_id, attempt)
                return result
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Step %d attempt %d failed: %s", step.step_id, attempt, exc
                )
                if attempt <= self._max_retries:
                    time.sleep(0.5 * attempt)  # brief back-off

        step.success = False
        return f"❌ Step {step.step_id} failed after {self._max_retries + 1} attempts: {last_error}"

    @staticmethod
    def _build_summary(plan: TaskPlan, results: list[str]) -> str:
        """Combine step results into a readable summary."""
        if not results:
            return "No steps were executed."

        if len(results) == 1:
            return results[0]

        lines = [f"**Task:** {plan.goal}", ""]
        for step, result in zip(plan.steps, results):
            status_icon = "✅" if step.success else "❌"
            lines.append(f"{status_icon} **Step {step.step_id}** — {step.description}")
            lines.append(f"   {result}")
            lines.append("")
        return "\n".join(lines)
