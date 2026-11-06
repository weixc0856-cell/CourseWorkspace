"""Runs inside the session container.

Only stdlib is available. It executes commands, captures stdout/stderr
separately, writes a structured transcript, and leaves assertions to the host
so that the verifier has a single implementation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback


def _emit(stream, text):
    if not text:
        return
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")
    stream.flush()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: runner.py <run.json> <raw-result.json>", file=sys.stderr)
        return 2
    spec_path, out_path = sys.argv[1], sys.argv[2]
    with open(spec_path, encoding="utf-8") as handle:
        spec = json.load(handle)
    workdir = spec.get("workdir", "/work")
    default_timeout = int(spec.get("timeout_s", 120))
    transcript_path = spec.get("transcript")
    transcript = open(transcript_path, "a", encoding="utf-8") if transcript_path else None

    results = []
    try:
        for command in spec["commands"]:
            command_id = command["id"]
            argv = command["run"]
            timeout = int(command.get("timeout_s", default_timeout))
            if transcript:
                transcript.write(f"\n=== {command_id} START ===\n")
                transcript.flush()
            started = time.monotonic()
            started_wall = time.time()
            timed_out = False
            env = os.environ.copy()
            env.setdefault("UV_CACHE_DIR", "/work/.uv-cache")
            env.setdefault("UV_PYTHON_INSTALL_DIR", "/work/.uv-python")
            env.setdefault("HOME", "/work/.home")
            for directory in (
                env["UV_CACHE_DIR"],
                env["UV_PYTHON_INSTALL_DIR"],
                env["HOME"],
            ):
                os.makedirs(directory, exist_ok=True)
            try:
                process = subprocess.run(
                    argv,
                    cwd=workdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
                exit_code = process.returncode
                stdout = process.stdout
                stderr = process.stderr
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                exit_code = 124
                stdout = exc.stdout if isinstance(exc.stdout, str) else ""
                stderr = exc.stderr if isinstance(exc.stderr, str) else ""
                stderr += f"\nTIMEOUT after {timeout} seconds"
            except Exception as exc:  # noqa: BLE001
                timed_out = False
                exit_code = None
                stdout = ""
                stderr = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            duration_ms = int((time.monotonic() - started) * 1000)
            finished_wall = time.time()
            _emit(sys.stdout, stdout)
            _emit(sys.stderr, stderr)
            if transcript:
                transcript.write(stdout)
                if stdout and not stdout.endswith("\n"):
                    transcript.write("\n")
                transcript.write(stderr)
                if stderr and not stderr.endswith("\n"):
                    transcript.write("\n")
                transcript.write(f"=== {command_id} END exit={exit_code} ===\n")
                transcript.flush()
            results.append(
                {
                    "id": command_id,
                    "argv": argv,
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "duration_ms": duration_ms,
                    "started_at": started_wall,
                    "finished_at": finished_wall,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
    finally:
        if transcript:
            transcript.close()
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump({"commands": results}, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
