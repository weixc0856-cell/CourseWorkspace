from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProcessResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


def run_command(
    command: list[str],
    cwd: Path,
    *,
    timeout: int,
    log_path: Path | None = None,
) -> ProcessResult:
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\nTIMEOUT after {timeout} seconds"
    duration_ms = int((time.monotonic() - started) * 1000)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "\n".join(
                [
                    "COMMAND: " + " ".join(command),
                    "CWD: " + str(cwd),
                    f"EXIT_CODE: {exit_code}",
                    f"DURATION_MS: {duration_ms}",
                    "--- STDOUT ---",
                    stdout,
                    "--- STDERR ---",
                    stderr,
                ]
            ),
            encoding="utf-8",
        )
    return ProcessResult(command, exit_code, stdout, stderr, duration_ms, timed_out)
