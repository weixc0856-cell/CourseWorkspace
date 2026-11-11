"""Run unittest discovery for one project and record console control events.

The hosted Windows runner runs each step in a console shared with its child
processes. This wrapper records every console control event (Ctrl+C,
Ctrl+Break, close, logoff, shutdown) to a file before letting the default
handling run, so an interrupted run can be told apart from a test failure.
Nothing here swallows an event: the handler returns FALSE, which keeps the
process exit behaviour unchanged.
"""
from __future__ import annotations

import ctypes
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_CTRL_EVENT_NAMES = {
    0: "CTRL_C_EVENT",
    1: "CTRL_BREAK_EVENT",
    2: "CTRL_CLOSE_EVENT",
    5: "CTRL_LOGOFF_EVENT",
    6: "CTRL_SHUTDOWN_EVENT",
}

_console_handler = None  # keeps the ctypes callback alive for the process


def event_log_path() -> Path:
    """Where console events are appended; overridable for local experiments."""
    raw = os.environ.get("CI_CONSOLE_EVENT_LOG")
    return Path(raw) if raw else Path("build") / "ci-console-events.log"


def record_event(path: Path, event: int, pid: int, ppid: int) -> str:
    """Append one console event line and return it."""
    name = _CTRL_EVENT_NAMES.get(int(event), "CTRL_%d" % int(event))
    line = "%s at=%s pid=%d ppid=%d" % (
        name,
        datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        pid,
        ppid,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return line


def install_console_event_log(pid: int) -> Path | None:
    """Record console control events without handling them."""
    if os.name != "nt":
        return None
    global _console_handler
    path = event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    def on_console_event(event: int) -> bool:
        try:
            line = record_event(path, event, pid, os.getppid())
        except OSError as exc:
            line = "console event %d at=%s pid=%d ppid=%d (log failed: %s)" % (
                int(event),
                datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                pid,
                os.getppid(),
                exc,
            )
        print("console event: " + line, file=sys.stderr, flush=True)
        return False  # not handled: the default behaviour still applies

    prototype = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    _console_handler = prototype(on_console_event)
    if not ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_handler, True):
        raise OSError(ctypes.get_last_error(), "SetConsoleCtrlHandler failed")
    return path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_tests_ci.py <start-dir> <top-level-dir>", file=sys.stderr)
        return 2
    start_dir, top_level = sys.argv[1], sys.argv[2]
    install_console_event_log(os.getpid())
    suite = unittest.TestLoader().discover(start_dir, top_level_dir=top_level)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
