from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_runtime.claude_code import (
    ClaudeCodeConfig,
    ClaudeCodeError,
    ClaudeCodeUnavailable,
    complete,
)


def payload(result: str = "OK") -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": result,
            "model": "deepseek-flash",
            "session_id": "session-test",
            "duration_ms": 12,
            "num_turns": 1,
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 2},
        }
    )


class ClaudeCodeTest(unittest.TestCase):
    def config(self, **overrides) -> ClaudeCodeConfig:
        values = dict(
            enabled=True,
            executable=sys.executable,
            model="deepseek-flash",
            timeout_s=30,
        )
        values.update(overrides)
        return ClaudeCodeConfig(**values)

    def test_text_mode_disables_tools_and_parses_result(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            return SimpleNamespace(returncode=0, stdout=payload('{"ok": true}'), stderr="")

        with patch("ai_runtime.claude_code.subprocess.run", side_effect=fake_run):
            result = complete(
                self.config(base_url="http://127.0.0.1:15721"),
                "do the task",
                system="system text",
            )
        self.assertEqual(result.content, '{"ok": true}')
        self.assertEqual(result.usage["num_turns"], 1)
        self.assertIn("--tools=", captured["command"])
        self.assertIn("--append-system-prompt", captured["command"])
        self.assertEqual(captured["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:15721")

    def test_agent_mode_uses_allowed_tools(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            return SimpleNamespace(returncode=0, stdout=payload(), stderr="")

        with patch("ai_runtime.claude_code.subprocess.run", side_effect=fake_run):
            complete(self.config(allowed_tools=("Read", "Write")), "task")
        self.assertIn("--permission-mode", captured["command"])
        self.assertTrue(
            any(str(arg).startswith("--allowedTools") for arg in captured["command"])
        )
        self.assertNotIn("--tools=", captured["command"])

    def test_agent_mode_requires_tools(self):
        with self.assertRaises(ClaudeCodeError):
            complete(self.config(), "task", tools=True)

    def test_nonzero_exit_is_an_error(self):
        with patch(
            "ai_runtime.claude_code.subprocess.run",
            return_value=SimpleNamespace(returncode=1, stdout="", stderr="boom"),
        ):
            with self.assertRaises(ClaudeCodeError):
                complete(self.config(), "task")

    def test_timeout_is_an_error(self):
        with patch(
            "ai_runtime.claude_code.subprocess.run",
            side_effect=subprocess.TimeoutExpired("claude", 30),
        ):
            with self.assertRaises(ClaudeCodeError):
                complete(self.config(), "task")

    def test_disabled_and_missing_executable(self):
        with self.assertRaises(ClaudeCodeUnavailable):
            complete(self.config(enabled=False), "task")
        with self.assertRaises(ClaudeCodeUnavailable):
            complete(self.config(executable="definitely-not-installed-xyz"), "task")

    def test_child_env_copies_named_token(self):
        os.environ["UNIT_TEST_CLAUDE_TOKEN"] = "secret-value"
        try:
            env = self.config(auth_token_env="UNIT_TEST_CLAUDE_TOKEN").child_env()
        finally:
            os.environ.pop("UNIT_TEST_CLAUDE_TOKEN", None)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "secret-value")


if __name__ == "__main__":
    unittest.main()
