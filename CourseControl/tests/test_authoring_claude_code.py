from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from course_control.authoring.llm import AuthoringBlocked, AuthoringClient, AuthoringConfig
from course_control.platform import workspace_layout


class Tiny(BaseModel):
    ok: bool


class AuthoringClaudeCodeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "authoring.yaml").write_text(
            "schema_version: 1" + chr(10) + "backend: claude_code" + chr(10), encoding="utf-8"
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

    def _with_content_root(self, content: Path):
        previous = os.environ.get(workspace_layout.ENV_VAR)
        os.environ[workspace_layout.ENV_VAR] = str(content)
        workspace_layout.reset_cache()
        return previous

    def _restore(self, previous):
        if previous is None:
            os.environ.pop(workspace_layout.ENV_VAR, None)
        else:
            os.environ[workspace_layout.ENV_VAR] = previous
        workspace_layout.reset_cache()

    def test_runtime_paths_default_to_the_content_root(self):
        content = self.root / "ContentRootA"
        content.mkdir()
        previous = self._with_content_root(content)
        try:
            config = AuthoringConfig.load(self.root)
            self.assertTrue(Path(config.lock_path).is_absolute())
            self.assertTrue(Path(config.lock_path).is_relative_to(content))
            self.assertTrue(Path(config.task_root).is_relative_to(content))
        finally:
            self._restore(previous)

    def test_relative_runtime_paths_resolve_under_the_content_root(self):
        content = self.root / "ContentRootB"
        content.mkdir()
        yaml_text = (
            "schema_version: 1" + chr(10)
            + "runtime:" + chr(10)
            + "  lock_path: runtime/locks/llama-8080.lock" + chr(10)
            + "  task_root: runtime/tasks" + chr(10)
        )
        (self.root / "config" / "authoring.yaml").write_text(yaml_text, encoding="utf-8")
        previous = self._with_content_root(content)
        try:
            config = AuthoringConfig.load(self.root)
            self.assertEqual(Path(config.lock_path), content / "runtime" / "locks" / "llama-8080.lock")
            self.assertEqual(Path(config.task_root), content / "runtime" / "tasks")
        finally:
            self._restore(previous)


if __name__ == "__main__":
    unittest.main()
