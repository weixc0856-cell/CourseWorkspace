"""Cross-process file lock with stale-lock recovery.

The lock is a file created with O_CREAT | O_EXCL. It records the owner PID,
task id, host and timestamps. A lock is considered stale when its owner PID is
gone or it is older than ``stale_after_s``.
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class LockTimeout(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class LockInfo:
    pid: int
    task_id: str
    host: str
    created_at: str
    acquired_at: float

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "task_id": self.task_id,
            "host": self.host,
            "created_at": self.created_at,
            "acquired_at": self.acquired_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockInfo":
        return cls(
            pid=int(data.get("pid", 0)),
            task_id=str(data.get("task_id", "")),
            host=str(data.get("host", "")),
            created_at=str(data.get("created_at", "")),
            acquired_at=float(data.get("acquired_at", 0.0)),
        )


class FileLock:
    """Cross-process mutex backed by an exclusively-created file."""

    def __init__(
        self,
        path: Path,
        *,
        task_id: str | None = None,
        timeout_s: float = 1800.0,
        stale_after_s: float = 3600.0,
        poll_s: float = 0.25,
    ):
        self.path = Path(path)
        self.task_id = task_id or uuid.uuid4().hex[:12]
        self.timeout_s = timeout_s
        self.stale_after_s = stale_after_s
        self.poll_s = poll_s
        self._held = False

    # -- inspection -----------------------------------------------------
    def read(self) -> LockInfo | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return None
        try:
            return LockInfo.from_dict(json.loads(raw))
        except (ValueError, TypeError):
            return None

    def is_stale(self, info: LockInfo | None) -> bool:
        if info is None:
            return True
        if not pid_alive(info.pid):
            return True
        return (time.time() - info.acquired_at) > self.stale_after_s

    # -- acquire / release ---------------------------------------------
    def acquire(self) -> "FileLock":
        deadline = time.monotonic() + self.timeout_s
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                info = self.read()
                if self.is_stale(info):
                    self._remove_if_unchanged(info)
                    continue
                if time.monotonic() >= deadline:
                    holder = f"pid={info.pid} task={info.task_id}" if info else "unknown"
                    raise LockTimeout(
                        f"timed out after {self.timeout_s:.0f}s waiting for {self.path} ({holder})"
                    )
                time.sleep(self.poll_s)
                continue
            info = LockInfo(
                pid=os.getpid(),
                task_id=self.task_id,
                host=socket.gethostname(),
                created_at=_now(),
                acquired_at=time.time(),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(info.to_dict(), handle)
                handle.flush()
                os.fsync(handle.fileno())
            self._held = True
            return self

    def _remove_if_unchanged(self, info: LockInfo | None) -> None:
        current = self.read()
        if info is None:
            if current is not None:
                return
        elif current is None or current.pid != info.pid or current.task_id != info.task_id:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def release(self) -> None:
        if not self._held:
            return
        current = self.read()
        if current is not None and current.pid == os.getpid() and current.task_id == self.task_id:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self._held = False

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
