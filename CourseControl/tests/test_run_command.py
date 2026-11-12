from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from course_control.platform.utils import run_command


class RunCommandTest(unittest.TestCase):
    def test_captures_stdout_and_writes_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_command(
                [sys.executable, "-c", "print('hello')"],
                root,
                timeout=30,
                log_path=root / "run.log",
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("hello", result.stdout)
            self.assertIn("EXIT_CODE: 0", (root / "run.log").read_text(encoding="utf-8"))

    def test_timeout_kills_the_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                Path(tmp),
                timeout=1,
            )
            self.assertTrue(result.timed_out)
            self.assertEqual(result.exit_code, 124)
            self.assertIn("TIMEOUT", result.stderr)


if __name__ == "__main__":
    unittest.main()
