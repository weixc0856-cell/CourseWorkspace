"""Session contracts for real code/terminal demonstrations (E0).

A session is executed once, recorded once, and produces three evidence channels:
machine result (stdout/stderr/exit code), PTY transcript, and the recording.
The contract is intentionally independent from the legacy narration/shot models.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*(?::[A-Za-z0-9._-]+)?(?:@sha256:[a-f0-9]{64})?$")


class SessionContractError(ValueError):
    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("\n".join(messages))


class FailureCode(str, Enum):
    ENVIRONMENT_FAILED = "environment_failed"
    EXECUTION_FAILED = "execution_failed"
    ASSERTION_FAILED = "assertion_failed"
    RECORDING_FAILED = "recording_failed"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    TIMEOUT = "timeout"
    TTS_UNAVAILABLE = "tts_unavailable"
    TTS_BUSY = "tts_busy"
    TTS_TIMEOUT = "tts_timeout"
    NARRATION_OVERFLOW = "narration_overflow"
    NARRATION_MISMATCH = "narration_mismatch"
    NETWORK_REQUIRED = "network_required"
    OFFLINE_VERIFY_FAILED = "offline_verify_failed"
    WAIT_TRIM_INVALID = "wait_trim_invalid"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _relative_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    if "\\" in value:
        raise ValueError(f"{label} must use '/' separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be relative and may not contain '..'")
    return path.as_posix()


class FileSpec(StrictModel):
    source: str
    path: str

    @field_validator("source", "path")
    @classmethod
    def _relative(cls, value: str, info):
        return _relative_path(value, info.field_name)


class SessionEnvironment(StrictModel):
    kind: Literal["docker", "wsl", "host"] = "docker"
    image: str | None = None
    user: str = "course"
    network: Literal["none", "bridge"] = "none"
    workdir: str = "/work"
    cpus: float = Field(2.0, gt=0.0, le=64.0)
    memory: str = Field("2g", pattern=r"^[0-9]+[bkmgBKMG]$")
    pids: int = Field(256, ge=16, le=65536)
    timeout_s: int = Field(120, ge=5, le=3600)

    @field_validator("image")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not IMAGE_RE.match(value):
            raise ValueError("image must be a valid docker reference")
        return value

    @model_validator(mode="after")
    def _image_required_for_docker(self):
        if self.kind == "docker" and not self.image:
            raise ValueError("docker environments require image")
        return self

    @field_validator("workdir")
    @classmethod
    def _workdir(cls, value: str) -> str:
        if not value.startswith("/") or ".." in value.split("/"):
            raise ValueError("workdir must be an absolute container path")
        return value


class Expect(StrictModel):
    exit_code: int = 0
    stdout: str | None = None
    stderr: str | None = None
    files: list[str] = Field(default_factory=list)

    @field_validator("stdout", "stderr")
    @classmethod
    def _optional_relative(cls, value: str | None, info):
        if value is None:
            return None
        return _relative_path(value, info.field_name)

    @field_validator("files")
    @classmethod
    def _files_relative(cls, value: list[str]) -> list[str]:
        return [_relative_path(item, "files[]") for item in value]


class Trim(StrictModel):
    command: str | None = None
    keep_head_s: float = Field(1.0, ge=0.0, le=60.0)
    keep_tail_s: float = Field(1.0, ge=0.0, le=60.0)
    max_wait_s: float | None = Field(None, gt=0.0, le=3600.0)


class CommandSpec(StrictModel):
    id: str
    run: list[str] = Field(min_length=1)
    expect: Expect = Expect()
    trim: Trim | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, value: str) -> str:
        if not ID_RE.match(value):
            raise ValueError("command id must match ^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
        return value

    @field_validator("run")
    @classmethod
    def _run(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item for item in value):
            raise ValueError("run entries must be non-empty strings")
        return value


class RecordSpec(StrictModel):
    target: Literal["terminal", "vscode"] = "terminal"
    capture: Literal["window", "desktop"] = "window"
    window_title: str = "CourseDemo"
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = Field(30, ge=1, le=120)

    @field_validator("window_title")
    @classmethod
    def _title(cls, value: str) -> str:
        if not value.strip() or any(char in value for char in "\r\n\"%"):
            raise ValueError("window_title must be a simple non-empty string")
        return value

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: tuple[int, int]) -> tuple[int, int]:
        if any(component < 320 or component > 8192 for component in value):
            raise ValueError("resolution components must be within 320..8192")
        return value


class SessionSpec(StrictModel):
    schema_version: Literal[1]
    lesson: str
    shot_id: str
    session_id: str
    environment: SessionEnvironment
    files: list[FileSpec] = Field(default_factory=list)
    commands: list[CommandSpec] = Field(min_length=1)
    record: RecordSpec = RecordSpec()
    typing_cps: float | None = Field(None, gt=0.0, le=240.0)

    @field_validator("lesson")
    @classmethod
    def _lesson(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson must be a lowercase slug")
        return value

    @field_validator("shot_id", "session_id")
    @classmethod
    def _identifier(cls, value: str) -> str:
        if not ID_RE.match(value):
            raise ValueError("must match ^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
        return value

    @model_validator(mode="after")
    def _integrity(self):
        ids = [command.id for command in self.commands]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate command ids: {duplicates}")
        targets = [file.path for file in self.files]
        duplicates = sorted({item for item in targets if targets.count(item) > 1})
        if duplicates:
            raise ValueError(f"duplicate file targets: {duplicates}")
        trim_commands = {item.command for item in (c.trim for c in self.commands) if item and item.command}
        unknown = sorted(trim_commands - set(ids))
        if unknown:
            raise ValueError(f"trim references unknown command: {unknown}")
        return self


class AssertionResult(StrictModel):
    name: str
    ok: bool
    detail: str = ""


class CommandResult(StrictModel):
    id: str
    argv: list[str]
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    stdout_sha256: str
    stderr_sha256: str
    assertions: list[AssertionResult] = Field(default_factory=list)


class EnvironmentResult(StrictModel):
    image: str | None = None
    image_digest: str | None = None
    network: str
    platform: str | None = None


class ExecutionResult(StrictModel):
    schema_version: Literal[1] = 1
    shot_id: str
    session_id: str
    status: Literal["passed", "failed"]
    failure: FailureCode | None = None
    commands: list[CommandResult] = Field(default_factory=list)
    environment: EnvironmentResult
    started_at: str
    finished_at: str


class RecordingResult(StrictModel):
    path: str
    sha256: str
    width: int
    height: int
    fps: float
    frames: int
    duration_s: float
    probe_ok: bool
    capture: Literal["window", "desktop"]


class EvidenceManifest(StrictModel):
    schema_version: Literal[1] = 1
    shot_id: str
    session_id: str
    spec_sha256: str
    execution_result: str | None = None
    recording_result: str | None = None
    validation_report: str | None = None
    transcript: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    cache_key: str


class FailureDetail(StrictModel):
    code: FailureCode
    message: str


class CheckResult(StrictModel):
    id: str
    status: Literal["pass", "fail", "not_applicable"]
    detail: str = ""


class ValidationReport(StrictModel):
    schema_version: Literal[1] = 1
    shot_id: str
    session_id: str
    status: Literal["pass", "fail"]
    failures: list[FailureDetail] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def normalize_stream(text: str) -> str:
    """Normalize terminal output for assertions.

    Keeping this in the contract module means the container runner and the
    host verifier share exactly one definition.
    """
    import re as _re

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    text = _re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def cache_key(
    spec: SessionSpec,
    file_hashes: dict[str, str],
    image_digest: str | None = None,
) -> str:
    payload = {
        "spec": spec.model_dump(mode="json"),
        "files": file_hashes,
        "image_digest": image_digest,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def load_session_spec(path: Path) -> SessionSpec:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionContractError([f"cannot read session spec: {exc}"]) from exc
    try:
        return SessionSpec.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        messages = []
        errors = getattr(exc, "errors", lambda: [])()
        for error in errors:
            location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
            messages.append(f"{location}: {error.get('msg', str(exc))}")
        raise SessionContractError(messages or [str(exc)]) from exc
