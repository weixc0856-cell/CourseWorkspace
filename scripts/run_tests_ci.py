"""Run unittest discovery with SIGINT ignored.

The hosted Windows runner occasionally delivers CTRL_C_EVENT to the test
process while it waits on ffmpeg or imports heavy modules. Python surfaces that
as KeyboardInterrupt inside an unrelated test. Ignoring SIGINT here keeps the
test process running; the runner still enforces its own job timeout.
"""
from __future__ import annotations

import signal
import sys
import unittest


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_tests_ci.py <start-dir> <top-level-dir>", file=sys.stderr)
        return 2
    start_dir, top_level = sys.argv[1], sys.argv[2]
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    suite = unittest.TestLoader().discover(start_dir, top_level_dir=top_level)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
