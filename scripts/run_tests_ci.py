"""Run unittest discovery for one project and record the console context.

Diagnostic for the hosted Windows runner: the test process receives a console
control event that nothing in the repository generates. This script records
who shares the console, the full ancestor chain, a per-test timeline and the
event itself, so the sender can be identified from evidence instead of guessed.
No event is handled and no exit behaviour is changed.
"""
from __future__ import annotations

import atexit
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
_context_handle = None

TH32CS_SNAPPROCESS = 0x00000002


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def event_log_path() -> Path:
    raw = os.environ.get("CI_CONSOLE_EVENT_LOG")
    return Path(raw) if raw else Path("build") / "ci-console-events.log"


def context_log_path() -> Path:
    raw = os.environ.get("CI_CONSOLE_CONTEXT_LOG")
    return Path(raw) if raw else Path("build") / "ci-console-context.log"


def _trace(line: str) -> None:
    handle = _context_handle
    if handle is None:
        return
    handle.write(line + "\n")
    handle.flush()


# --- Windows process table, console membership and ancestry (ctypes only) ---

if os.name == "nt":

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_uint32),
            ("cntUsage", ctypes.c_uint32),
            ("th32ProcessID", ctypes.c_uint32),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", ctypes.c_uint32),
            ("cntThreads", ctypes.c_uint32),
            ("th32ParentProcessID", ctypes.c_uint32),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_uint32),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    _kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    _kernel32.Process32FirstW.restype = ctypes.c_int
    _kernel32.Process32FirstW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_PROCESSENTRY32W),
    ]
    _kernel32.Process32NextW.restype = ctypes.c_int
    _kernel32.Process32NextW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_PROCESSENTRY32W),
    ]
    _kernel32.CloseHandle.restype = ctypes.c_int
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.GetConsoleProcessList.restype = ctypes.c_uint32
    _kernel32.GetConsoleProcessList.argtypes = [
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_uint32,
    ]
    _kernel32.SetConsoleCtrlHandler.restype = ctypes.c_int
    _kernel32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, ctypes.c_int]


def process_table() -> dict[int, tuple[int, str]]:
    """Map every visible pid to (parent pid, executable name)."""
    if os.name != "nt":
        return {}
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return {}
    table: dict[int, tuple[int, str]] = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            table[int(entry.th32ProcessID)] = (
                int(entry.th32ParentProcessID),
                entry.szExeFile,
            )
            ok = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    return table


def console_process_ids() -> list[int]:
    """PIDs of every process sharing this process's console."""
    if os.name != "nt":
        return []
    array = (ctypes.c_uint32 * 256)()
    count = _kernel32.GetConsoleProcessList(array, 256)
    if count <= 0:
        return []
    return [int(array[index]) for index in range(min(int(count), 256))]


def console_window() -> int:
    if os.name != "nt":
        return 0
    return int(ctypes.windll.kernel32.GetConsoleWindow())


def ancestor_chain(
    table: dict[int, tuple[int, str]], pid: int, limit: int = 12
) -> list[tuple[int, int, str]]:
    chain: list[tuple[int, int, str]] = []
    seen: set[int] = set()
    current = pid
    while current and current not in seen and len(chain) < limit:
        seen.add(current)
        parent, name = table.get(current, (0, "?"))
        chain.append((current, parent, name))
        current = parent
    return chain


def record_event(
    path: Path, event: int, pid: int, ppid: int, pids: list[int] | None = None
) -> str:
    name = _CTRL_EVENT_NAMES.get(int(event), "CTRL_%d" % int(event))
    line = "%s at=%s pid=%d ppid=%d" % (name, _now(), pid, ppid)
    if pids is not None:
        line += " console_pids=" + ",".join(str(item) for item in pids)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return line


def log_context(pid: int, project: str) -> None:
    if _context_handle is None:
        return
    table = process_table()
    pids = console_process_ids()
    _trace(
        "RUN_START at=%s pid=%d ppid=%d project=%s"
        % (_now(), pid, os.getppid(), project)
    )
    _trace(
        "CONSOLE at=%s window=%d processes=%d pids=%s"
        % (_now(), console_window(), len(pids), ",".join(str(item) for item in pids))
    )
    for cpid in pids:
        parent, name = table.get(cpid, (0, "?"))
        _trace("CONSOLE_PROC pid=%d ppid=%d exe=%s" % (cpid, parent, name))
    for cpid, parent, name in ancestor_chain(table, pid):
        _trace("ANCESTOR pid=%d ppid=%d exe=%s" % (cpid, parent, name))


def install_console_event_log(pid: int) -> Path | None:
    if os.name != "nt":
        return None
    global _console_handler
    path = event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    def on_console_event(event: int) -> bool:
        pids = console_process_ids()
        try:
            line = record_event(path, event, pid, os.getppid(), pids)
        except OSError as exc:
            line = "console event %d at=%s pid=%d ppid=%d (log failed: %s)" % (
                int(event),
                _now(),
                pid,
                os.getppid(),
                exc,
            )
        _trace("CONSOLE_EVENT " + line)
        print("console event: " + line, file=sys.stderr, flush=True)
        # The hosted Windows runner sends a real Ctrl-C into this process while
        # the suite runs, which surfaces as KeyboardInterrupt inside whatever
        # test happens to be executing (usually a server shutdown).  Record it
        # and stay alive: the signal is the runner's, not the tests'.
        if event in (0, 1):  # CTRL_C_EVENT, CTRL_BREAK_EVENT
            return True
        return False  # close/logoff/shutdown still mean the process must go

    prototype = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint32)
    _console_handler = prototype(on_console_event)
    if not _kernel32.SetConsoleCtrlHandler(_console_handler, 1):
        raise OSError(ctypes.get_last_error(), "SetConsoleCtrlHandler failed")
    return path


class _TracingResult(unittest.TextTestResult):
    def startTest(self, test) -> None:
        super().startTest(test)
        _trace("TEST_START at=%s test=%s" % (_now(), test.id()))


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: run_tests_ci.py <start-dir> <top-level-dir>", file=sys.stderr)
        return 2
    start_dir, top_level = sys.argv[1], sys.argv[2]
    global _context_handle
    context = context_log_path()
    context.parent.mkdir(parents=True, exist_ok=True)
    _context_handle = context.open("a", encoding="utf-8")
    pid = os.getpid()
    log_context(pid, top_level)
    install_console_event_log(pid)

    def _on_exit() -> None:
        _trace("PROCESS_EXIT at=%s pid=%d" % (_now(), pid))

    atexit.register(_on_exit)
    suite = unittest.TestLoader().discover(start_dir, top_level_dir=top_level)
    runner = unittest.TextTestRunner(verbosity=1, resultclass=_TracingResult)
    result = runner.run(suite)
    successful = result.wasSuccessful()
    _trace(
        "RUN_END at=%s tests=%d failures=%d errors=%d skipped=%d successful=%s"
        % (
            _now(),
            result.testsRun,
            len(result.failures),
            len(result.errors),
            len(result.skipped),
            successful,
        )
    )
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
