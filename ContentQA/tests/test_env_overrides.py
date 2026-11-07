from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from content_qa.config import ConfigError, load_config


def _config(model: str = "deepseek-v4-pro") -> dict:
    return {
        "schema_version": 1,
        "model": {
            "base_url": "https://api.deepseek.com",
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


class ContentQAEnvOverrideTest(unittest.TestCase):
    def test_env_flash_overrides_yaml_pro(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "content-qa.yaml"
            path.write_text(
                yaml.safe_dump(_config("deepseek-v4-pro"), allow_unicode=True),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
                    "DEEPSEEK_MODEL": "deepseek-flash",
                },
            ):
                config = load_config(path)
        self.assertIsNotNone(config)
        self.assertEqual(config.model.model, "deepseek-flash")

    def test_env_pro_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "content-qa.yaml"
            path.write_text(
                yaml.safe_dump(_config("deepseek-flash"), allow_unicode=True),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DEEPSEEK_MODEL": "deepseek-v4-pro"}):
                with self.assertRaises(ConfigError):
                    load_config(path)


if __name__ == "__main__":
    unittest.main()
