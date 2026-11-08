"""Claude Code CLI as a text-generation / agent backend.

This module only shells out to the installed ``claude`` executable and parses
its JSON result. It never stores credentials: the child process inherits the
environment, optionally with ``ANTHROPIC_BASE_URL`` and an auth token copied
from a named environment variable.

Text mode (default) disables every tool with ``--tools ""`` so callers get a
plain completion. Agent mode is opt-in through ``allowed_tools`` and is meant
for staged workspaces (for example a Code2Video shot directory), never for
``lessons/``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ALLOWED_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep")


class ClaudeCodeError(RuntimeError):
    """The CLI failed, timed out, or returned an unusable payload."""


class ClaudeCodeUnavailable(ClaudeCodeError):
    """The configured executable is missing."""


@dataclass
class ClaudeCodeConfig:
    enabled: bool = False
    executable: str = "claude"
    model: str = "deepseek-flash"
    timeout_s: int = 900
    max_turns: int = 1
    base_url: str | None = None
    auth_token_env: str | None = None
    permission_mode: str = "acceptEdits"
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, data: dict) -> "ClaudeCodeConfig":
        tools = data.get("allowed_tools")
        if tools is None:
            tools = ()
        elif isinstance(tools, str):
            tools = tuple(part.strip() for part in tools.split(",") if part.strip())
        else:
            tools = tuple(str(part) for part in tools)
        return cls(
            enabled=bool(data.get("enabled", False)),
            executable=str(data.get("executable", "claude")),
            model=str(data.get("model", "deepseek-flash")),
            timeout_s=int(data.get("timeout_s", 900)),
            max_turns=int(data.get("max_turns", 1)),
            base_url=(str(data["base_url"]) if data.get("base_url") else None),
            auth_token_env=(
                str(data["auth_token_env"]) if data.get("auth_token_env") else None
            ),
            permission_mode=str(data.get("permission_mode", "acceptEdits")),
            allowed_tools=tools,
        )

    def resolved_executable(self) -> str:
        executable = self.executable
        if os.path.sep in executable or (os.altsep and os.altsep in executable):
            return executable
        if os.name == "nt":
            # npm installs ``claude``, ``claude.cmd`` and a ``claude.exe`` shim
            # that points at the .cmd file; CreateProcess cannot run the bare
            # shim or the symlink. Prefer the real node_modules executable so
            # arguments such as an empty --tools value survive intact.
            command_shim = shutil.which(executable + ".cmd")
            if command_shim:
                bundled = (
                    Path(command_shim).parent
                    / "node_modules"
                    / "@anthropic-ai"
                    / "claude-code"
                    / "bin"
                    / "claude.exe"
                )
                if bundled.is_file():
                    return str(bundled)
                return command_shim
            for suffix in (".bat", ".exe"):
                found = shutil.which(executable + suffix)
                if found:
                    return found
        return shutil.which(executable) or executable

    def available(self) -> bool:
        executable = self.resolved_executable()
        if os.path.sep in executable or (os.altsep and os.altsep in executable):
            return Path(executable).is_file()
        return shutil.which(executable) is not None

    def child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.base_url:
            env["ANTHROPIC_BASE_URL"] = self.base_url
        if self.auth_token_env:
            token = os.environ.get(self.auth_token_env)
            if token:
                env["ANTHROPIC_AUTH_TOKEN"] = token
        return env


@dataclass
class ClaudeCodeResult:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    session_id: str | None = None
    duration_ms: int | None = None
    total_cost_usd: float | None = None
    raw: dict = field(default_factory=dict)


def _command(
    config: ClaudeCodeConfig,
    prompt: str,
    *,
    system: str | None,
    tools: bool,
) -> list[str]:
    command = [
        config.resolved_executable(),
        "-p",
        "--output-format",
        "json",
        "--model",
        config.model,
        "--max-turns",
        str(config.max_turns),
    ]
    if system:
        command.extend(["--append-system-prompt", system])
    if tools:
        command.extend(
            [
                "--permission-mode",
                config.permission_mode,
                "--allowedTools=" + ",".join(config.allowed_tools),
            ]
        )
    else:
        command.append("--tools=")
    command.append(prompt)
    return command


def _parse_stdout(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise ClaudeCodeError(f"claude returned no JSON payload: {text[:500]}")
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ClaudeCodeError(f"claude returned invalid JSON: {exc}: {text[:500]}") from exc
    if not isinstance(data, dict):
        raise ClaudeCodeError("claude returned JSON that is not an object")
    return data


def complete(
    config: ClaudeCodeConfig,
    prompt: str,
    *,
    system: str | None = None,
    cwd: Path | str | None = None,
    timeout_s: int | None = None,
    tools: bool | None = None,
) -> ClaudeCodeResult:
    """Run one Claude Code task and return its final text.

    ``tools`` defaults to False when ``allowed_tools`` is empty (text-only) and
    True otherwise. Passing ``tools=True`` without allowed tools raises.
    """
    if not config.enabled:
        raise ClaudeCodeUnavailable("claude-code backend is disabled")
    if not config.available():
        raise ClaudeCodeUnavailable(f"claude executable not found: {config.executable}")
    use_tools = bool(config.allowed_tools) if tools is None else tools
    if use_tools and not config.allowed_tools:
        raise ClaudeCodeError("agent mode requires at least one allowed tool")
    command = _command(config, prompt, system=system, tools=use_tools)
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=config.child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s or config.timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCodeError(
            f"claude timed out after {timeout_s or config.timeout_s}s"
        ) from exc
    except OSError as exc:
        raise ClaudeCodeUnavailable(f"cannot launch claude: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise ClaudeCodeError(f"claude exited {proc.returncode}: {detail}")
    data = _parse_stdout(proc.stdout or "")
    if data.get("is_error"):
        raise ClaudeCodeError(
            f"claude reported an error: {str(data.get('result') or data)[:800]}"
        )
    content = data.get("result")
    if not isinstance(content, str) or not content.strip():
        raise ClaudeCodeError(
            f"claude returned empty result; reason={data.get('terminal_reason') or data.get('subtype')}"
        )
    usage = dict(data.get("usage") or {})
    usage.setdefault("num_turns", data.get("num_turns"))
    usage.setdefault("duration_ms", data.get("duration_ms"))
    usage.setdefault("total_cost_usd", data.get("total_cost_usd"))
    return ClaudeCodeResult(
        content=content,
        model=str(data.get("model") or config.model),
        usage=usage,
        session_id=data.get("session_id"),
        duration_ms=data.get("duration_ms"),
        total_cost_usd=data.get("total_cost_usd"),
        raw=data,
    )


__all__ = [
    "DEFAULT_ALLOWED_TOOLS",
    "ClaudeCodeConfig",
    "ClaudeCodeError",
    "ClaudeCodeResult",
    "ClaudeCodeUnavailable",
    "complete",
]
