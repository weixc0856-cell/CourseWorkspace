from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .paths import ContractError


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


@dataclass
class MediaInfo:
    duration: float | None
    width: int | None
    height: int | None
    fps: float | None
    codec: str | None
    pix_fmt: str | None
    has_audio: bool
    audio_duration: float | None

    def as_dict(self) -> dict:
        return {
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "codec": self.codec,
            "pix_fmt": self.pix_fmt,
            "has_audio": self.has_audio,
            "audio_duration": self.audio_duration,
        }


def which_command(name: str) -> list[str]:
    path = shutil.which(name)
    if not path:
        return [name]
    if path.lower().endswith((".cmd", ".bat")):
        return ["cmd.exe", "/c", path]
    return [path]


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(os.getpgid(pid), 15)
        except (OSError, ProcessLookupError):
            pass


def run_command(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 1800,
    log_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run a command with a hard timeout.

    Output is redirected to temporary files rather than pipes: on Windows a
    renderer can spawn a child that inherits the pipe and keeps it open after
    the parent exits, which makes ``subprocess.run(capture_output=True)`` wait
    forever.  ``Popen.wait`` returns when the launched process exits.
    """
    started = time.monotonic()
    timed_out = False
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    with tempfile.TemporaryDirectory() as temp_dir:
        stdout_path = Path(temp_dir) / "stdout.txt"
        stderr_path = Path(temp_dir) / "stderr.txt"
        with stdout_path.open("w", encoding="utf-8", errors="replace") as out_handle, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as err_handle:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=child_env,
                stdout=out_handle,
                stderr=err_handle,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = 124
                _kill_process_tree(process.pid)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            except BaseException:
                _kill_process_tree(process.pid)
                raise
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    if timed_out:
        stderr += chr(10) + f"TIMEOUT after {timeout} seconds"
    duration_ms = int((time.monotonic() - started) * 1000)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            chr(10).join(
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

    return CommandResult(command, exit_code, stdout, stderr, duration_ms, timed_out)


def probe_media(path: Path) -> MediaInfo:
    if not path.is_file():
        raise ContractError(f"media not found: {path}")
    command = which_command("ffprobe") + [
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    result = run_command(command, path.parent, timeout=60)
    if result.exit_code != 0:
        raise ContractError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise ContractError(f"no video stream: {path}")

    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    frame_rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    try:
        numerator, denominator = frame_rate.split("/")
        fps = float(numerator) / float(denominator) if float(denominator) else None
    except (ValueError, ZeroDivisionError):
        fps = None

    duration = number(video.get("duration")) or number(data.get("format", {}).get("duration"))
    audio_duration = number(audio.get("duration")) if audio else None
    return MediaInfo(
        duration=duration,
        width=video.get("width"),
        height=video.get("height"),
        fps=fps,
        codec=video.get("codec_name"),
        pix_fmt=video.get("pix_fmt"),
        has_audio=audio is not None,
        audio_duration=audio_duration,
    )


def notes_blocks(notes_text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^###\s+Slide\s+([0-9]+[a-z]?)\b.*$", notes_text, re.M))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(notes_text)
        blocks.append((match.group(1), notes_text[match.start():end]))
    return blocks


def page_budgets(notes_text: str) -> list[float]:
    budgets: list[float] = []
    for label, block in notes_blocks(notes_text):
        match = re.search(
            r"时长预算\**\s*[：:]\s*([0-9]+(?:\.[0-9]+)?)\s*(秒|s|分钟|min)",
            block,
            re.I,
        )
        if not match:
            raise ContractError(f"Slide {label} has no parseable 时长预算")
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit in ("分钟", "min"):
            value *= 60
        budgets.append(value)
    if not budgets:
        raise ContractError("no page budgets found in lecture_notes.md")
    return budgets


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise ContractError(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc


def count_srt_cues(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len([line for line in text.splitlines() if "-->" in line])


def probe_audio(path: Path) -> float:
    """Return the duration of the first audio stream."""
    if not path.is_file():
        raise ContractError(f"audio not found: {path}")
    command = which_command("ffprobe") + [
        "-v", "error", "-show_streams", "-of", "json", str(path),
    ]
    result = run_command(command, path.parent, timeout=60)
    if result.exit_code != 0:
        raise ContractError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    streams = json.loads(result.stdout or "{}").get("streams", [])
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if audio is None:
        raise ContractError(f"no audio stream: {path}")
    try:
        duration = float(audio.get("duration"))
    except (TypeError, ValueError):
        duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0.0))
    return duration
