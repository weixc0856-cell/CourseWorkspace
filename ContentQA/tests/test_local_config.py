from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from content_qa.config import load_config


class LocalEndpointTests(unittest.TestCase):
    def test_local_endpoint_is_not_rewritten_by_remote_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "content-qa-local.yaml"
            path.write_text(
                """schema_version: 1
backend: api
model:
  base_url: "http://127.0.0.1:8080/v1"
  model: "Qwen3-30B-A3B-Instruct-2507"
  api_key_env: "CONTENT_QA_LOCAL_KEY"
""",
                encoding="utf-8",
            )
            old = {key: os.environ.get(key) for key in ("REMOTE_MODEL", "REMOTE_BASE_URL")}
            os.environ["REMOTE_MODEL"] = "deepseek-flash"
            os.environ["REMOTE_BASE_URL"] = "https://api.deepseek.com/v1"
            try:
                config = load_config(path)
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            self.assertIsNotNone(config)
            assert config is not None
            self.assertEqual(config.model.base_url, "http://127.0.0.1:8080/v1")
            self.assertEqual(config.model.model, "Qwen3-30B-A3B-Instruct-2507")


if __name__ == "__main__":
    unittest.main()
