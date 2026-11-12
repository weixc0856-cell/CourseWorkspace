from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from course_control.platform.build_lock import BuildLock, BuildLockError


class BuildLockTest(unittest.TestCase):
    def test_second_acquire_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            first = BuildLock(workspace, "demo")
            first.acquire()
            try:
                with self.assertRaises(BuildLockError):
                    BuildLock(workspace, "demo").acquire()
            finally:
                first.release()
            second = BuildLock(workspace, "demo")
            second.acquire()
            second.release()

    @unittest.skipIf(os.environ.get("CI") == "true", "stale lock reclaim is flaky on Windows CI")
    def test_stale_lock_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = workspace / "runtime" / "locks" / "build-demo.lock"
            path.parent.mkdir(parents=True)
            path.write_text("99999999\n2026-01-01T00:00:00+00:00\n", encoding="utf-8")
            lock = BuildLock(workspace, "demo")
            lock.acquire()
            self.assertTrue(path.is_file())
            lock.release()
            self.assertFalse(path.is_file())


if __name__ == "__main__":
    unittest.main()
