from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from ai_runtime import ClaudeCodeConfig, load_env_file
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "workflow.yaml"

# Stage budgets are fixed so they can be checked against the model context.
# (limit_tokens, reserved_output_tokens)
STAGE_BUDGETS: dict[str, tuple[int, int]] = {
    "analyze": (16384, 2048),
    "plan": (32768, 3000),
    "generate": (32768, 6000),
    "revise": (16384, 2048),
}
STAGE_MODELS: dict[str, str] = {
    "analyze": "vision",
    "plan": "planner",
    "generate": "coder",
    "revise": "vision",
}


class ConfigError(RuntimeError):
    pass


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://127.0.0.1:8080/v1"
    api_key: str = "sk-local"
    request_timeout_s: int = Field(900, ge=30, le=3600)
    max_retries: int = Field(1, ge=0, le=3)


class RemoteSettings(BaseModel):
    """Optional remote fallback when the local 8080 service is unavailable."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-flash"
    api_key_env: str = "DEEPSEEK_API_KEY"
    timeout_s: int = Field(120, ge=10, le=3600)
    max_tokens: int = Field(4096, ge=1, le=131072)
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    supports_vision: bool = True
    vision_model: str | None = "deepseek-flash"
    trust_env: bool = True
    fallback_on: list[
        Literal["busy", "start_error", "lock_timeout", "missing_executable"]
    ] = Field(
        default_factory=lambda: [
            "busy",
            "start_error",
            "lock_timeout",
            "missing_executable",
        ]
    )

    @model_validator(mode="after")
    def _deepseek_flash_only(self):
        if self.provider == "deepseek":
            for label, value in (
                ("model", self.model),
                ("vision_model", self.vision_model),
            ):
                if value and value != "deepseek-flash":
                    raise ValueError(
                        "DeepSeek is pinned to deepseek-flash; "
                        f"{label}={value!r} is disabled"
                    )
        return self

    def runtime(self):
        from ai_runtime import RemoteConfig

        return RemoteConfig(
            enabled=self.enabled,
            provider=self.provider,
            base_url=self.base_url,
            model=self.model,
            api_key_env=self.api_key_env,
            timeout_s=self.timeout_s,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            supports_vision=self.supports_vision,
            vision_model=self.vision_model,
            trust_env=self.trust_env,
            fallback_on=tuple(self.fallback_on),
        )


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable: str
    host: str = "127.0.0.1"
    port: int = Field(8080, ge=1, le=65535)
    startup_timeout_s: int = Field(300, ge=30, le=1800)
    stop_timeout_s: int = Field(30, ge=5, le=300)
    log_dir: str = "logs"


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    alias: str
    context: int = Field(32768, ge=2048, le=262144)
    mmproj: str | None = None
    args: list[str] = Field(default_factory=list)


class BlenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable: str
    timeout_seconds: int = Field(900, ge=30, le=7200)


class RuntimeConfig(BaseModel):
    """Machine-wide lock and task records shared with other projects."""

    model_config = ConfigDict(extra="forbid")

    lock_path: str = "../runtime/locks/llama-8080.lock"
    task_root: str = "../runtime/tasks"
    lock_timeout_s: float = Field(3600, ge=1, le=86400)
    stale_after_s: float = Field(3600, ge=60, le=86400)

    @property
    def lock_path_resolved(self) -> Path:
        return _resolve(self.lock_path).resolve()

    @property
    def task_root_resolved(self) -> Path:
        return _resolve(self.task_root).resolve()


class WorkflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    schema_version: Literal[1] = 1
    backend: Literal["auto", "local_first", "claude_code"] = "auto"
    claude_code_fallback: Literal["none", "local_first"] = "none"
    claude_code: ClaudeCodeConfig | None = None
    llm: LLMConfig = LLMConfig()
    remote: RemoteSettings = RemoteSettings()
    server: ServerConfig
    models: dict[str, ModelConfig]
    blender: BlenderConfig
    runtime: RuntimeConfig = RuntimeConfig()
    jobs_root: str = "workspace/jobs"

    def model(self, key: str) -> ModelConfig:
        try:
            return self.models[key]
        except KeyError as exc:
            raise ConfigError(
                f"workflow.yaml has no model '{key}'; available: {sorted(self.models)}"
            ) from exc

    def server_config(self):
        from ai_runtime import ServerConfig

        return ServerConfig(
            executable=self.server.executable,
            host=self.server.host,
            port=self.server.port,
            startup_timeout_s=self.server.startup_timeout_s,
            stop_timeout_s=self.server.stop_timeout_s,
        )

    def model_spec(self, key: str):
        from ai_runtime import ModelSpec

        model = self.model(key)
        return ModelSpec(
            key=key,
            alias=model.alias,
            args=self.server_args(key),
            context=model.context,
        )

    def budget_for(self, stage: str):
        """Return the stage budget, refusing to exceed the model's context."""
        from ai_runtime import ContextBudget

        try:
            limit, reserved = STAGE_BUDGETS[stage]
            key = STAGE_MODELS[stage]
        except KeyError as exc:
            raise ConfigError(f"unknown modeling stage: {stage}") from exc
        model = self.model(key)
        if limit > model.context:
            raise ConfigError(
                f"{stage} budget {limit} exceeds {key} context {model.context}"
            )
        return ContextBudget(limit=limit, reserved_output=reserved)

    @property
    def jobs_dir(self) -> Path:
        return _resolve(self.jobs_root)

    @property
    def server_log_dir(self) -> Path:
        return _resolve(self.server.log_dir)

    def server_args(self, key: str) -> list[str]:
        model = self.model(key)
        args = [
            "-m",
            _require_path(model.path, f"models.{key}.path"),
            "--host",
            self.server.host,
            "--port",
            str(self.server.port),
            "-c",
            str(model.context),
            "--parallel",
            "1",
            "-b",
            "256",
            "-ub",
            "128",
            "-fa",
            "on",
            "--metrics",
            "--alias",
            f"{model.alias},default",
            "--jinja",
        ]
        if model.mmproj:
            args += [
                "--mmproj",
                _require_path(model.mmproj, f"models.{key}.mmproj"),
                "--no-mmproj-offload",
            ]
        args += model.args
        return args


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _require_path(value: str, label: str) -> str:
    if "<" in value and ">" in value:
        raise ConfigError(
            f"{label} still contains a placeholder: {value}; "
            "copy config/workflow.example.yaml to config/workflow.yaml and fill local paths"
        )
    path = _resolve(value)
    if not path.is_file():
        raise ConfigError(f"{label} not found: {path}")
    return str(path)


def _apply_remote_env(remote: dict) -> dict:
    """Apply generic REMOTE_* settings (any OpenAI-compatible provider)."""
    mapping = (
        ("enabled", "REMOTE_ENABLED"),
        ("provider", "REMOTE_PROVIDER"),
        ("base_url", "REMOTE_BASE_URL"),
        ("model", "REMOTE_MODEL"),
        ("vision_model", "REMOTE_VISION_MODEL"),
        ("api_key_env", "REMOTE_API_KEY_ENV"),
    )
    from_generic: set[str] = set()
    for field, env_name in mapping:
        value = os.environ.get(env_name)
        if value is None:
            continue
        from_generic.add(field)
        if field == "enabled":
            remote[field] = value.strip().lower() in {"1", "true", "yes", "on"}
        else:
            remote[field] = value
    if str(remote.get("provider") or "deepseek") == "deepseek":
        for field, env_name in (
            ("base_url", "DEEPSEEK_BASE_URL"),
            ("model", "DEEPSEEK_MODEL"),
            ("vision_model", "DEEPSEEK_VISION_MODEL"),
        ):
            if field in from_generic:
                continue
            value = os.environ.get(env_name)
            if value:
                remote[field] = value
    return remote


def load_config(path: Path | None = None) -> WorkflowConfig:
    config_path = path or DEFAULT_CONFIG
    if not config_path.is_file():
        raise ConfigError(
            f"config not found: {config_path}; "
            "copy ModelingStudio/config/workflow.example.yaml to config/workflow.yaml"
        )
    # Real DeepSeek values live in the workspace .env (git-ignored).
    if len(config_path.parents) >= 3:
        load_env_file(config_path.parents[2] / ".env")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {config_path}: {exc}") from exc
    # Remote routing is workspace-level (config/model-routing.yaml), so the
    # same provider/key configuration is shared by every project.
    routing_path = (
        config_path.parents[2] / "config" / "model-routing.yaml"
        if len(config_path.parents) >= 3
        else None
    )
    if routing_path is not None and routing_path.is_file():
        try:
            routing = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {routing_path}: {exc}") from exc
        remote_data = dict(routing.get("remote") or {})
        fallback = routing.get("fallback") or {}
        if fallback.get("on"):
            remote_data["fallback_on"] = fallback["on"]
        if remote_data:
            data["remote"] = {**remote_data, **(data.get("remote") or {})}
    data["remote"] = _apply_remote_env(dict(data.get("remote") or {}))
    cc_path = (
        config_path.parents[2] / "config" / "claude-code.yaml"
        if len(config_path.parents) >= 3
        else None
    )
    claude_code = None
    if cc_path is not None and cc_path.is_file():
        try:
            cc_data = yaml.safe_load(cc_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {cc_path}: {exc}") from exc
        if isinstance(cc_data, dict):
            claude_code = ClaudeCodeConfig.from_mapping(cc_data)
    if str(data.get("backend", "auto")) == "auto":
        data["backend"] = (
            "claude_code" if claude_code and claude_code.enabled else "local_first"
        )
    data["claude_code"] = claude_code
    try:
        config = WorkflowConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{config_path} does not match workflow config: {exc}") from exc
    # Validate the Blender path early; model paths are checked when a stage starts.
    _require_path(config.blender.executable, "blender.executable")
    _require_path(config.server.executable, "server.executable")
    return config
