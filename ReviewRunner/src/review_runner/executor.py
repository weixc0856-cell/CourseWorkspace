"""Codex CLI executor with a measured, isolated invocation.

Measured on this machine (2026-11-08, codex-cli 0.167.0, DeepSeek provider):

* user config (MCP servers + model catalog + host skills): 19,238 input tokens
  for a trivial request;
* isolated invocation (``--ignore-user-config`` + explicit provider using an
  environment variable for the key): 14,243 input tokens.

The isolated form is the default: it disables the machine's MCP servers and
plugins for our runs, never reads or copies the credential, and keeps the
provider key in the child process environment only.  Host skill discovery still
scans ``~/.agents/skills`` in this version; that warning is filtered and
recorded, not treated as a finding.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .privacy import endpoint_host

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_KEY_ENV = "DeepSeek-API"
WIRE_API = "responses"

MEASURED_USER_CONFIG_INPUT = 19238
MEASURED_ISOLATED_INPUT = 14243
MEASURED_DATE = "2026-11-08"


class ExecutorError(RuntimeError):
    """The CLI is missing or the invocation cannot be built."""


@dataclass(frozen=True)
class CodexSettings:
    executable: str = "codex"
    sandbox: str = "read-only"
    isolated: bool = True
    provider: str = "deepseek"
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key_env: str = DEFAULT_KEY_ENV
    wire_api: str = WIRE_API

    def validate_model(self) -> None:
        parts = self.model.lower().replace("_", "-").split("-")
        if "pro" in parts:
            raise ExecutorError(
                f"model {self.model!r} is disabled by project policy; "
                "DeepSeek runs are pinned to a flash model"
            )


@dataclass(frozen=True)
class ProviderInfo:
    provider: str | None
    model: str | None
    endpoint_host: str | None
    isolation: str
    base_url: str | None


def load_project_remote(workspace: Path) -> dict:
    """Read provider settings from the git-ignored project routing config.

    The file names an environment variable; it never contains a key.  Missing
    or unreadable config falls back to the project DeepSeek defaults.
    """
    path = workspace / "config" / "model-routing.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml  # imported lazily so tests do not need the project config
    except ImportError:  # pragma: no cover - dependency is declared
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):  # type: ignore[attr-defined]
        return {}
    remote = data.get("remote")
    return remote if isinstance(remote, dict) else {}


def settings_for(workspace: Path, *, isolated: bool = True) -> CodexSettings:
    remote = load_project_remote(workspace)
    settings = CodexSettings(
        isolated=isolated,
        provider=str(remote.get("provider") or "deepseek"),
        model=str(remote.get("model") or DEFAULT_MODEL),
        base_url=str(remote.get("base_url") or DEFAULT_BASE_URL),
        api_key_env=str(remote.get("api_key_env") or DEFAULT_KEY_ENV),
    )
    settings.validate_model()
    return settings


def provider_info(settings: CodexSettings) -> ProviderInfo:
    return ProviderInfo(
        provider=settings.provider,
        model=settings.model,
        endpoint_host=endpoint_host(settings.base_url),
        isolation="isolated" if settings.isolated else "user-config",
        base_url=settings.base_url,
    )


def resolve_executable(name: str) -> str:
    if os.path.sep in name or (os.altsep and os.altsep in name):
        return name
    if os.name == "nt":
        for suffix in (".cmd", ".exe", ".bat"):
            found = shutil.which(name + suffix)
            if found:
                return found
    return shutil.which(name) or name


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_argv(
    settings: CodexSettings,
    *,
    executable: str,
    cwd: Path,
    prompt: str | None = None,
) -> list[str]:
    argv = [executable, "exec"]
    if settings.isolated:
        provider_table = (
            "{name=\"ReviewRunner\","
            f"base_url={_toml_string(settings.base_url)},"
            f"wire_api={_toml_string(settings.wire_api)},"
            f"env_key={_toml_string(settings.api_key_env)},"
            "requires_openai_auth=false}"
        )
        argv.extend(
            [
                "--ignore-user-config",
                "-c",
                f"model={_toml_string(settings.model)}",
                "-c",
                'model_provider="review"',
                "-c",
                f"model_providers.review={provider_table}",
            ]
        )
    argv.extend(
        [
            "-s",
            settings.sandbox,
            "--ephemeral",
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(cwd),
            "-",
        ]
    )
    return argv


@dataclass
class ExecutionResult:
    argv: list[str]
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    duration_ms: int
    started_at: str
    finished_at: str
    launcher_error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        import signal

        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def run_process(
    argv: list[str],
    *,
    cwd: Path,
    timeout_s: int,
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
) -> tuple[int | None, bool, bytes, bytes, int]:
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        **kwargs,
    )
    started = time.monotonic()
    timed_out = False
    payload = stdin_text.encode("utf-8") if stdin_text is not None else None
    try:
        stdout, stderr = proc.communicate(input=payload, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            stdout, stderr = b"", b"timeout: process tree did not exit"
    duration_ms = int((time.monotonic() - started) * 1000)
    return proc.returncode, timed_out, stdout, stderr, duration_ms


class CodexExecutor(Protocol):
    def run(self, prompt: str, cwd: Path, timeout_s: int) -> ExecutionResult: ...


@dataclass
class RealCodexExecutor:
    settings: CodexSettings = field(default_factory=CodexSettings)

    def run(self, prompt: str, cwd: Path, timeout_s: int) -> ExecutionResult:
        executable = resolve_executable(self.settings.executable)
        if not executable:
            raise ExecutorError("codex executable not found")
        argv = build_argv(
            self.settings,
            executable=executable,
            cwd=cwd,
            prompt=prompt,
        )
        env = os.environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("NO_COLOR", "1")
        started_at = _now()
        try:
            code, timed_out, stdout, stderr, duration_ms = run_process(
                argv,
                cwd=cwd,
                timeout_s=timeout_s,
                env=env,
                stdin_text=prompt,
            )
        except OSError as exc:
            return ExecutionResult(
                argv=argv,
                exit_code=None,
                timed_out=False,
                stdout="",
                stderr="",
                duration_ms=0,
                started_at=started_at,
                finished_at=_now(),
                launcher_error=f"cannot launch codex: {exc}",
            )
        return ExecutionResult(
            argv=argv,
            exit_code=code,
            timed_out=timed_out,
            stdout=(stdout or b"").decode("utf-8", "replace"),
            stderr=(stderr or b"").decode("utf-8", "replace"),
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=_now(),
        )


@dataclass
class FakeCodexExecutor:
    """Scripted executor for tests; consumes no external tokens."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    duration_ms: int = 5
    on_run: Callable[[Path], None] | None = None
    calls: list[Path] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def run(self, prompt: str, cwd: Path, timeout_s: int) -> ExecutionResult:
        self.calls.append(cwd)
        self.prompts.append(prompt)
        if self.on_run is not None:
            self.on_run(cwd)
        return ExecutionResult(
            argv=["fake-codex", "exec", "-C", str(cwd)],
            exit_code=self.exit_code,
            timed_out=self.timed_out,
            stdout=self.stdout,
            stderr=self.stderr,
            duration_ms=self.duration_ms,
            started_at=_now(),
            finished_at=_now(),
        )


__all__ = [
    "CodexExecutor",
    "CodexSettings",
    "DEFAULT_BASE_URL",
    "DEFAULT_KEY_ENV",
    "DEFAULT_MODEL",
    "ExecutionResult",
    "ExecutorError",
    "FakeCodexExecutor",
    "MEASURED_DATE",
    "MEASURED_ISOLATED_INPUT",
    "MEASURED_USER_CONFIG_INPUT",
    "ProviderInfo",
    "RealCodexExecutor",
    "build_argv",
    "load_project_remote",
    "provider_info",
    "resolve_executable",
    "run_process",
    "settings_for",
]
