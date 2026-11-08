from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from course_control.authoring.llm import AuthoringBlocked, AuthoringClient, AuthoringConfig


class Tiny(BaseModel):
    ok: bool


class AuthoringClaudeCodeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "authoring.yaml").write_text(
            "schema_version: 1\nbackend: claude_code\n", encoding="utf-8"
        )
        (self.root / "config" / "claude-code.yaml").write_text(
            "enabled: true\nexecutable: claude\nmodel: deepseek-flash\ntimeout_s: 30\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_config_selects_claude_code(self):
        config = AuthoringConfig.load(self.root)
        self.assertEqual(config.backend, "claude_code")
        self.assertTrue(config.claude_code is not None and config.claude_code.enabled)

    def test_client_uses_claude_route_without_local_service(self):
        config = AuthoringConfig.load(self.root)
        with patch.object(
            type(config.claude_code), "available", return_value=True
        ), AuthoringClient(config) as client:
            self.assertEqual(client.route.provider, "claude_code")
            self.assertEqual(client.route.model, "deepseek-flash")

    def test_unavailable_without_fallback_is_blocked(self):
        config = AuthoringConfig.load(self.root)
        with patch.object(
            type(config.claude_code), "available", return_value=False
        ):
            with self.assertRaises(AuthoringBlocked):
                with AuthoringClient(config):
                    pass

    def test_chat_json_uses_text_mode_and_system_prompt(self):
        config = AuthoringConfig.load(self.root)
        captured = {}

        def fake_complete(cc, prompt, **kwargs):
            captured["prompt"] = prompt
            captured.update(kwargs)
            return SimpleNamespace(content='{"ok": true}', usage={"output_tokens": 4})

        with patch.object(
            type(config.claude_code), "available", return_value=True
        ), patch("course_control.authoring.llm.claude_code_complete", side_effect=fake_complete):
            with AuthoringClient(config) as client:
                result = client.chat_json(
                    [
                        {"role": "system", "content": "system rules"},
                        {"role": "user", "content": "make it"},
                    ],
                    Tiny,
                    task_type="test.claude_code",
                )
        self.assertTrue(result.ok)
        self.assertIn("system rules", captured["system"])
        self.assertIn("make it", captured["prompt"])
        self.assertFalse(captured["tools"])


if __name__ == "__main__":
    unittest.main()
