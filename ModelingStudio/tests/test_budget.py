from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

import httpx

from ai_runtime import ContextBudget, ContextOverflow
from ai_runtime.budget import HARD_LIMIT
from modeling_studio.config import STAGE_BUDGETS, ConfigError, WorkflowConfig
from modeling_studio.llm import LLMClient, LLMError


def make_config(root: Path, planner_context: int = 32768) -> WorkflowConfig:
    return WorkflowConfig.model_validate(
        {
            "schema_version": 1,
            "server": {"executable": str(root / "llama-server.exe")},
            "models": {
                "vision": {
                    "path": str(root / "vision.gguf"),
                    "alias": "vision-alias",
                    "context": 16384,
                },
                "planner": {
                    "path": str(root / "planner.gguf"),
                    "alias": "planner-alias",
                    "context": planner_context,
                },
                "coder": {
                    "path": str(root / "coder.gguf"),
                    "alias": "coder-alias",
                    "context": 32768,
                },
            },
            "blender": {"executable": str(root / "blender.exe")},
        }
    )


class BudgetAlignmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = make_config(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_each_stage_budget_fits_its_model_context(self):
        for stage in STAGE_BUDGETS:
            budget = self.config.budget_for(stage)
            self.assertEqual(budget.limit, STAGE_BUDGETS[stage][0])
            self.assertEqual(budget.reserved_output, STAGE_BUDGETS[stage][1])
            self.assertLessEqual(budget.limit, HARD_LIMIT)

    def test_misconfigured_context_is_rejected(self):
        config = make_config(self.root, planner_context=8192)
        with self.assertRaises(ConfigError):
            config.budget_for("plan")

    def test_hard_ceiling_cannot_be_exceeded(self):
        with self.assertRaises(ValueError):
            ContextBudget(limit=65537)

    def test_retry_cannot_bypass_budget(self):
        """The client re-checks on every attempt, not just the first."""
        budget = ContextBudget(limit=200, reserved_output=20)
        client = LLMClient(self.config, budget=budget)
        messages = [{"role": "user", "content": "字" * 500}]
        with self.assertRaises(ContextOverflow):
            client.chat(messages, "planner")

    def test_request_timeout_raises_llm_error(self):
        client = LLMClient(self.config)
        with unittest.mock.patch(
            "httpx.Client.post", side_effect=httpx.ReadTimeout("timeout")
        ):
            with self.assertRaises(LLMError):
                client.chat([{"role": "user", "content": "hi"}], "planner", max_tokens=8)


if __name__ == "__main__":
    unittest.main()
