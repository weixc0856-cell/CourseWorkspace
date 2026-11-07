from __future__ import annotations

import unittest

from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from ai_runtime import ClaudeCodeConfig
from content_qa.client import OnlineClient
from content_qa.config import ReviewConfig


def _config(model: str, base_url: str = "https://api.deepseek.com") -> dict:
    return {
        "schema_version": 1,
        "model": {
            "base_url": base_url,
            "model": model,
            "api_key_env": "DeepSeek-API",
            "timeout_s": 60,
            "max_tokens": 1024,
            "temperature": 0.0,
            "retries": 1,
        },
        "context_limit": 16384,
        "sources_file": "sources.yaml",
    }


class DeepSeekModelPolicyTest(unittest.TestCase):
    def test_deepseek_flash_is_accepted(self):
        config = ReviewConfig.model_validate(_config("deepseek-flash"))
        self.assertEqual(config.model.model, "deepseek-flash")

    def test_deepseek_pro_is_rejected(self):
        with self.assertRaises(ValidationError):
            ReviewConfig.model_validate(_config("deepseek-v4-pro"))

    def test_non_deepseek_provider_is_not_restricted(self):
        config = ReviewConfig.model_validate(
            _config("some-other-model", base_url="https://api.example.com/v1")
        )
        self.assertEqual(config.model.model, "some-other-model")

    def test_claude_code_backend_returns_json_without_api_key(self):
        data = _config("deepseek-flash")
        data["backend"] = "claude_code"
        data["claude_code"] = ClaudeCodeConfig(
            enabled=True, executable="claude", model="deepseek-flash"
        )
        config = ReviewConfig.model_validate(data)
        client = OnlineClient(config)
        with patch(
            "content_qa.client.claude_code_complete",
            return_value=SimpleNamespace(
                content='{"ok": true}', usage={"input_tokens": 5}
            ),
        ) as mocked:
            result, usage = client.chat_json(
                [{"role": "user", "content": "review this"}]
            )
        self.assertTrue(result["ok"])
        self.assertEqual(usage["input_tokens"], 5)
        self.assertFalse(mocked.call_args.kwargs["tools"])


if __name__ == "__main__":
    unittest.main()
