from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_runtime import load_env_file


class EnvFileTest(unittest.TestCase):
    def test_loads_values_without_overriding_existing_env(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text(
                "DEEPSEEK_MODEL=deepseek-flash\n"
                "DEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"DEEPSEEK_MODEL": "from-shell"},
                clear=False,
            ):
                loaded = load_env_file(path)
                self.assertEqual(loaded["DEEPSEEK_MODEL"], "deepseek-flash")
                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "from-shell")
                self.assertEqual(
                    os.environ["DEEPSEEK_BASE_URL"], "https://api.deepseek.com/v1"
                )

    def test_override_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text("DEEPSEEK_MODEL=deepseek-flash\n", encoding="utf-8")
            with patch.dict(os.environ, {"DEEPSEEK_MODEL": "from-shell"}, clear=False):
                load_env_file(path, override=True)
                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "deepseek-flash")


if __name__ == "__main__":
    unittest.main()
