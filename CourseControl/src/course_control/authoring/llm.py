"""Local-first LLM client for authoring drafts (R1-5A).

Reuses ``shared.ai_runtime`` for the 8080 lock, service lifecycle, routing,
context budget and task records. No new dependencies: HTTP is urllib.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from ai_runtime import (
    ClaudeCodeConfig,
    ClaudeCodeError,
    ClaudeCodeUnavailable,
    ContextBudget,
    ContextOverflow,
    FileLock,
    ModelSpec,
    ModelRoute,
    RemoteConfig,
    ServerBusy,
    ServerConfig,
    ServerStartError,
    TaskRecord,
    TaskStore,
    claude_code_complete,
    is_healthy,
    route_model,
)


class AuthoringError(RuntimeError):
    pass


class AuthoringBlocked(AuthoringError):
    pass


@dataclass
class AuthoringConfig:
    workspace: Path
    server_executable: str
    host: str = "127.0.0.1"
    port: int = 8080
    startup_timeout_s: int = 300
    stop_timeout_s: int = 30
    model_path: str = ""
    model_alias: str = "Qwen3-30B-A3B-Instruct-2507"
    model_context: int = 32768
    model_args: list[str] = field(default_factory=list)
    context_limit: int = 32768
    reserved_output: int = 4096
    request_timeout_s: int = 900
    max_retries: int = 1
    temperature: float = 0.2
    remote_thinking: str = "disabled"
    lock_path: str = "runtime/locks/llama-8080.lock"
    task_root: str = "runtime/tasks"
    lock_timeout_s: int = 3600
    stale_after_s: int = 3600
    backend: str = "auto"
    claude_code_fallback: str = "none"
    remote: RemoteConfig | None = None
    claude_code: ClaudeCodeConfig | None = None

    @classmethod
    def load(cls, workspace: Path) -> "AuthoringConfig":
        workspace = workspace.resolve()
        path = workspace / "config" / "authoring.yaml"
        if not path.is_file():
            raise AuthoringBlocked(
                "config/authoring.yaml not found; copy config/authoring.example.yaml"
            )
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        server = data.get("server") or {}
        model = data.get("model") or {}
        llm = data.get("llm") or {}
        runtime = data.get("runtime") or {}
        remote = None
        routing = workspace / "config" / "model-routing.yaml"
        if routing.is_file():
            route_data = yaml.safe_load(routing.read_text(encoding="utf-8")) or {}
            remote_data = route_data.get("remote") or {}
            if remote_data:
                remote = RemoteConfig(
                    enabled=bool(remote_data.get("enabled", False)),
                    provider=str(remote_data.get("provider", "deepseek")),
                    base_url=str(remote_data.get("base_url", "https://api.deepseek.com/v1")),
                    model=str(remote_data.get("model", "deepseek-flash")),
                    api_key_env=str(remote_data.get("api_key_env", "DEEPSEEK_API_KEY")),
                    timeout_s=int(remote_data.get("timeout_s", 120)),
                    supports_vision=bool(remote_data.get("supports_vision", False)),
                    vision_model=remote_data.get("vision_model"),
                )
        claude_code = None
        cc_path = workspace / "config" / "claude-code.yaml"
        if cc_path.is_file():
            try:
                cc_data = yaml.safe_load(cc_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise AuthoringBlocked(f"invalid YAML in {cc_path}: {exc}") from exc
            if not isinstance(cc_data, dict):
                raise AuthoringBlocked(f"{cc_path} must contain a YAML mapping")
            claude_code = ClaudeCodeConfig.from_mapping(cc_data)
        backend = str(data.get("backend", "auto"))
        if backend == "auto":
            backend = "claude_code" if claude_code and claude_code.enabled else "local_first"
        return cls(
            workspace=workspace,
            server_executable=str(server.get("executable", "")),
            host=str(server.get("host", "127.0.0.1")),
            port=int(server.get("port", 8080)),
            startup_timeout_s=int(server.get("startup_timeout_s", 300)),
            stop_timeout_s=int(server.get("stop_timeout_s", 30)),
            model_path=str(model.get("path", "")),
            model_alias=str(model.get("alias", "Qwen3-30B-A3B-Instruct-2507")),
            model_context=int(model.get("context", 32768)),
            model_args=[str(item) for item in (model.get("args") or [])],
            context_limit=int(llm.get("context_limit", 32768)),
            reserved_output=int(llm.get("reserved_output", 4096)),
            request_timeout_s=int(llm.get("request_timeout_s", 900)),
            max_retries=int(llm.get("max_retries", 1)),
            temperature=float(llm.get("temperature", 0.2)),
            remote_thinking=str(llm.get("remote_thinking", "disabled")),
            lock_path=str(runtime.get("lock_path", "runtime/locks/llama-8080.lock")),
            task_root=str(runtime.get("task_root", "runtime/tasks")),
            lock_timeout_s=int(runtime.get("lock_timeout_s", 3600)),
            stale_after_s=int(runtime.get("stale_after_s", 3600)),
            backend=backend,
            claude_code_fallback=str(data.get("claude_code_fallback", "none")),
            remote=remote,
            claude_code=claude_code,
        )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _task_id(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{stamp}-{os.getpid()}"


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AuthoringError("model reply contains no JSON object")
    candidates = [cleaned[start : end + 1]]
    # Some providers emit literal newlines/tabs inside JSON strings.
    candidates.append(
        candidates[0].replace("\r", " ").replace("\n", " ").replace("\t", " ")
    )
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            raise AuthoringError("model JSON must be an object")
        return data
    raise AuthoringError(f"invalid JSON from model: {last_error}")


class AuthoringClient:
    """Context-managed local-first chat client."""

    def __init__(
        self,
        config: AuthoringConfig,
        *,
        start_service: bool = True,
        remote_only: bool = False,
    ):
        self.config = config
        self.start_service = start_service
        self.remote_only = remote_only
        self._stack = ExitStack()
        self.route = None
        self.tasks = TaskStore(config.workspace / config.task_root)

    def __enter__(self) -> "AuthoringClient":
        if self.config.backend == "claude_code" and not self.remote_only:
            cc = self.config.claude_code
            if cc is not None and cc.enabled and cc.available():
                self.route = ModelRoute(
                    provider="claude_code",
                    base_url="",
                    api_key="",
                    model=cc.model,
                    mode="claude_code",
                )
                return self
            detail = (
                "claude-code backend is not available"
                if cc is None or not cc.enabled
                else f"claude executable not found: {cc.executable}"
            )
            if self.config.claude_code_fallback != "local_first":
                raise AuthoringBlocked(
                    f"{detail}; set backend=local_first or claude_code_fallback=local_first"
                )
        if self.remote_only:
            remote = self.config.remote
            if remote is None or not remote.enabled:
                raise AuthoringBlocked("remote provider is not enabled in config/model-routing.yaml")
            key = remote.resolved_key()
            if not key:
                raise AuthoringBlocked(
                    f"remote API key is missing: env {remote.api_key_env}"
                )
            self.route = ModelRoute(
                provider="remote",
                base_url=remote.base_url.rstrip("/"),
                api_key=key,
                model=remote.model_for(),
                mode="remote",
                context_limit=None,
                vision=False,
                trust_env=remote.trust_env,
            )
            return self
        if not self.config.server_executable:
            raise AuthoringBlocked("server.executable is empty in config/authoring.yaml")
        server = ServerConfig(
            executable=self.config.server_executable,
            host=self.config.host,
            port=self.config.port,
            startup_timeout_s=self.config.startup_timeout_s,
            stop_timeout_s=self.config.stop_timeout_s,
        )
        if not self.start_service and not is_healthy(server):
            raise AuthoringBlocked(
                "local model is not running and --no-start-service was requested; "
                "start 8080 or omit --no-start-service"
            )
        if not self.config.model_path:
            raise AuthoringBlocked("model.path is empty in config/authoring.yaml")
        model = ModelSpec(
            key="planner",
            alias=self.config.model_alias,
            args=[
                "-m",
                self.config.model_path,
                "--alias",
                self.config.model_alias,
                "--host",
                self.config.host,
                "--port",
                str(self.config.port),
                "--parallel",
                "1",
                *self.config.model_args,
                "-c",
                str(self.config.model_context),
            ],
            context=self.config.model_context,
        )
        lock = FileLock(
            self.config.workspace / self.config.lock_path,
            timeout_s=self.config.lock_timeout_s,
            stale_after_s=self.config.stale_after_s,
        )
        log_path = self.config.workspace / "build" / "authoring" / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.route = self._stack.enter_context(
                route_model(
                    server,
                    model,
                    lock,
                    log_path,
                    remote=self.config.remote,
                )
            )
        except (ServerBusy, ServerStartError, Exception) as exc:
            self._stack.close()
            name = type(exc).__name__
            if name in {"ServerBusy", "ServerStartError", "LockTimeout"}:
                raise AuthoringBlocked(f"local model unavailable: {name}: {exc}") from exc
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stack.close()

    def _post(self, messages: list[dict], *, max_tokens: int, json_object: bool = False) -> tuple[str, dict]:
        assert self.route is not None
        if self.route.provider == "claude_code":
            return self._post_claude_code(messages, max_tokens=max_tokens, json_object=json_object)
        payload = {
            "model": self.route.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.config.temperature,
        }
        if json_object:
            payload["response_format"] = {"type": "json_object"}
        if (
            self.route.provider == "remote"
            and self.config.remote_thinking
            and self.config.remote is not None
            and self.config.remote.provider == "deepseek"
        ):
            payload["thinking"] = {"type": self.config.remote_thinking}
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.route.base_url.rstrip("/") + "/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.route.api_key}",
            },
            method="POST",
        )
        if self.route.trust_env:
            opener = urllib.request.build_opener()
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=self.config.request_timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise AuthoringError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AuthoringError(f"model request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AuthoringError(f"unexpected chat payload: {str(body)[:500]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise AuthoringError(f"model returned empty content; raw={str(body)[:800]}")
        usage = dict(body.get("usage") or {})
        usage["finish_reason"] = body["choices"][0].get("finish_reason")
        return content, usage

    def _post_claude_code(
        self, messages: list[dict], *, max_tokens: int, json_object: bool
    ) -> tuple[str, dict]:
        cc = self.config.claude_code
        if cc is None:
            raise AuthoringError("claude-code backend is not configured")
        system = "\n\n".join(
            str(item.get("content", "")) for item in messages if item.get("role") == "system"
        )
        body = "\n\n".join(
            f"{str(item.get('role', 'user')).upper()}:\n{item.get('content', '')}"
            for item in messages
            if item.get("role") != "system"
        )
        if json_object:
            body += (
                "\n\nReturn only one JSON object that validates the requested schema. "
                "No markdown fences, no commentary."
            )
        try:
            result = claude_code_complete(
                cc,
                body,
                system=system or None,
                timeout_s=self.config.request_timeout_s,
                tools=False,
            )
        except ClaudeCodeUnavailable as exc:
            raise AuthoringBlocked(str(exc)) from exc
        except ClaudeCodeError as exc:
            raise AuthoringError(str(exc)) from exc
        return result.content, result.usage

    def chat(
        self,
        messages: list[dict],
        *,
        task_type: str,
        input_artifacts: list[str] | None = None,
        max_tokens: int | None = None,
        task_id: str | None = None,
        json_object: bool = False,
    ) -> str:
        assert self.route is not None
        budget = ContextBudget(
            limit=self.config.context_limit,
            reserved_output=max_tokens or self.config.reserved_output,
        )
        try:
            report = budget.check(messages)
        except ContextOverflow as exc:
            raise AuthoringError(str(exc)) from exc
        task_id = task_id or _task_id(task_type)
        record = TaskRecord(
            task_id=task_id,
            task_type=task_type,
            assigned_model=self.route.model,
            provider=self.route.provider,
            status="running",
            input_artifacts=list(input_artifacts or []),
            context_budget=report.as_dict(),
            timeout_s=self.config.request_timeout_s,
            retry_policy={"max_attempts": self.config.max_retries + 1, "backoff_s": 1},
            started_at=_now(),
        )
        self.tasks.save(record)
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                content, usage = self._post(
                    messages,
                    max_tokens=max_tokens or self.config.reserved_output,
                    json_object=json_object,
                )
            except AuthoringError as exc:
                last_error = exc
                continue
            record.status = "completed"
            record.finished_at = _now()
            record.error = None
            self.tasks.save(record)
            return content
        record.status = "failed"
        record.error = str(last_error)
        record.finished_at = _now()
        self.tasks.save(record)
        raise AuthoringError(str(last_error))

    def chat_json(
        self,
        messages: list[dict],
        model_type,
        *,
        task_type: str,
        input_artifacts: list[str] | None = None,
        max_tokens: int | None = None,
    ):
        content = self.chat(
            messages,
            task_type=task_type,
            input_artifacts=input_artifacts,
            max_tokens=max_tokens,
            json_object=True,
        )
        try:
            return model_type.model_validate(extract_json(content))
        except Exception as exc:  # noqa: BLE001
            repair = {
                "role": "user",
                "content": (
                    "Your previous reply was not valid for the required JSON schema. "
                    f"Error: {exc}. Return only the corrected JSON object."
                ),
            }
            content = self.chat(
                [*messages, {"role": "assistant", "content": content}, repair],
                task_type=task_type + ".repair",
                input_artifacts=input_artifacts,
                max_tokens=max_tokens,
                json_object=True,
            )
            return model_type.model_validate(extract_json(content))
