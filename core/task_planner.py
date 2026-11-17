"""
core/task_planner.py
--------------------
Breaks a user request into a sequence of executable steps using the AI engine.
Each step has an intent, parameters, and a description.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from core.ai_engine import AIEngine

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """A single step in a multi-step task plan."""
    step_id: int
    description: str
    intent: str
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    result: str | None = None
    success: bool | None = None


@dataclass
class TaskPlan:
    """An ordered list of steps for completing a user request."""
    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    completed: bool = False
    final_summary: str = ""

    def __len__(self) -> int:
        return len(self.steps)

    def next_pending(self) -> TaskStep | None:
        """Return the first step that has not yet been executed."""
        for step in self.steps:
            if step.success is None:
                # Check dependencies are satisfied
                deps_ok = all(
                    any(s.step_id == dep and s.success for s in self.steps)
                    for dep in step.depends_on
                )
                if deps_ok or not step.depends_on:
                    return step
        return None


class TaskPlanner:
    """
    Uses the AI engine to decompose a complex request into a TaskPlan.

    For simple requests it may return a single-step plan.
    For multi-step tasks it asks the LLM to produce a JSON plan.
    """

    _PLANNING_SYSTEM_PROMPT = """You are a task-planning assistant.
Given a user goal, output a JSON array of steps, each step being:
{
  "step_id": <int starting at 1>,
  "description": "<what this step does>",
  "intent": "<one of: SYSTEM_MONITOR, OPEN_APP, FILE_OPERATION, WEB_SEARCH, NOTIFY, RUN_COMMAND, CHAT>",
  "params": { <key-value pairs the tool needs> },
  "depends_on": [<list of step_ids this step must wait for, or empty list>]
}

Output ONLY the JSON array — no prose, no markdown fences.
If the goal is simple and needs only one step, still output a single-element array.
"""

    def __init__(self, ai_engine: AIEngine) -> None:
        self._ai = ai_engine

    def create_plan(self, goal: str, context: list[dict[str, str]] | None = None) -> TaskPlan:
        """
        Produce a TaskPlan for *goal*.

        Args:
            goal:    The user's request / goal string.
            context: Optional prior conversation for context injection.

        Returns:
            A TaskPlan ready for the ExecutionEngine.
        """
        logger.info("Planning task: %.80s", goal)

        # Quick heuristic: single-intent requests get a fast plan
        single = self._try_single_step(goal)
        if single is not None:
            logger.debug("Single-step fast-path for goal.")
            return TaskPlan(goal=goal, steps=[single])

        # Ask the AI to decompose the goal
        messages = [
            {"role": "system", "content": self._PLANNING_SYSTEM_PROMPT},
        ]
        if context:
            messages += context[-4:]  # last 4 turns for context
        messages.append({"role": "user", "content": f"Goal: {goal}"})

        try:
            raw = self._ai.chat(messages, stream=False)
            steps = self._parse_plan(raw)
            if steps:
                logger.info("Plan created with %d step(s).", len(steps))
                return TaskPlan(goal=goal, steps=steps)
        except Exception as exc:
            logger.error("Planning failed: %s — falling back to single CHAT step.", exc)

        # Fallback: treat as a plain chat
        fallback = TaskStep(
            step_id=1,
            description="Answer the user directly.",
            intent="CHAT",
            params={"query": goal},
        )
        return TaskPlan(goal=goal, steps=[fallback])

    # ── Helpers ───────────────────────────────────────────────────────────────

    _SIMPLE_INTENTS: dict[str, str] = {
        "cpu": "SYSTEM_MONITOR",
        "ram": "SYSTEM_MONITOR",
        "memory": "SYSTEM_MONITOR",
        "battery": "SYSTEM_MONITOR",
        "disk": "SYSTEM_MONITOR",
        "open": "OPEN_APP",
        "launch": "OPEN_APP",
        "search": "WEB_SEARCH",
        "notify": "NOTIFY",
        "notification": "NOTIFY",
    }

    def _try_single_step(self, goal: str) -> TaskStep | None:
        """
        Fast-path: return a pre-built step for obviously simple goals.
        Returns None if the goal is not trivially classifiable.
        """
        lower = goal.lower()

        # System monitor shortcuts
        for keyword, intent in self._SIMPLE_INTENTS.items():
            if keyword in lower:
                params: dict[str, Any] = {}
                if intent == "SYSTEM_MONITOR":
                    params["metric"] = keyword if keyword in (
                        "cpu", "ram", "battery", "disk", "memory"
                    ) else "all"
                elif intent == "WEB_SEARCH":
                    params["query"] = goal
                elif intent == "OPEN_APP":
                    # Extract app name heuristically
                    words = lower.split()
                    idx = words.index(keyword) if keyword in words else -1
                    app = words[idx + 1] if idx >= 0 and idx + 1 < len(words) else goal
                    params["app"] = app
                return TaskStep(
                    step_id=1,
                    description=f"Handle '{intent}' request.",
                    intent=intent,
                    params=params,
                )
        return None

    def _parse_plan(self, raw: str) -> list[TaskStep]:
        """Parse JSON array from the AI planner response."""
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            data: list[dict[str, Any]] = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Expected a JSON array.")
            steps = [
                TaskStep(
                    step_id=item.get("step_id", idx + 1),
                    description=item.get("description", ""),
                    intent=item.get("intent", "CHAT"),
                    params=item.get("params", {}),
                    depends_on=item.get("depends_on", []),
                )
                for idx, item in enumerate(data)
            ]
            return steps
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Could not parse plan JSON: %s", exc)
            return []
