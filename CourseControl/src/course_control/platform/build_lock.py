"""One build per lesson.

Two builds writing the same staging directory at once can corrupt each other:
one `stage-assets` run replaces files while the other renderer is reading them.
The lock is a file in `runtime/locks/`, created atomically; a stale lock whose
PID is gone is reclaimed.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from course_control.platform.workspace_layout import runtime_root


class BuildLockError(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _pid_alive_windows(pid: int) -> bool:
    """Probe liveness without ``os.kill``.

    ``CTRL_C_EVENT`` is 0 on Windows, so ``os.kill(pid, 0)`` is not a probe
    there: CPython calls ``GenerateConsoleCtrlEvent(0, pid)`` and sends a real
    Ctrl+C to console process group ``pid``.  Ask the kernel instead.
    """
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    error_access_denied = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        # Access denied means the process exists but we may not open it.
        return ctypes.get_last_error() == error_access_denied
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


class BuildLock:
    def __init__(self, workspace: Path, slug: str):
        self.path = runtime_root(workspace) / "locks" / f"build-{slug}.lock"
        self.slug = slug
        self._owned = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                descriptor = os.open(
                    self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
                )
            except FileExistsError:
                try:
                    content = self.path.read_text(encoding="utf-8").strip().splitlines()
                    pid = int(content[0]) if content else 0
                except (OSError, ValueError):
                    pid = 0
                if pid and _pid_alive(pid):
                    raise BuildLockError(
                        f"another build is already running for {self.slug} (pid {pid})"
                    )
                # Stale lock: remove and retry once.
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                if attempt == 0:
                    continue
                raise BuildLockError(f"cannot acquire build lock: {self.path}")
            else:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(f"{os.getpid()}\n")
                    handle.write(datetime.now(timezone.utc).isoformat(timespec="seconds") + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                self._owned = True
                return
        raise BuildLockError(f"cannot acquire build lock: {self.path}")

    def release(self) -> None:
        if not self._owned:
            return
        try:
            lines = self.path.read_text(encoding="utf-8").strip().splitlines()
            owner = int(lines[0]) if lines else 0
            if owner == os.getpid():
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
        finally:
            self._owned = False

    def __enter__(self) -> "BuildLock":
        self.acquire()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


__all__ = ["BuildLock", "BuildLockError"]
