from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from ai_runtime import load_env_file
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT.parent / "config" / "content-qa.yaml"


class ConfigError(RuntimeError):
    pass


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "https://api.example.com/v1"
    model: str
    api_key_env: str = "CONTENT_QA_API_KEY"
    api_key: str | None = None
    timeout_s: int = Field(120, ge=1, le=1800)
    max_tokens: int = Field(2048, ge=256, le=32000)
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    retries: int = Field(1, ge=0, le=5)

    @model_validator(mode="after")
    def _deepseek_flash_only(self):
        if "deepseek" in self.base_url.lower() and self.model != "deepseek-flash":
            raise ValueError(
                "DeepSeek reviews are pinned to deepseek-flash; "
                f"model={self.model!r} is disabled"
            )
        return self


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    model: ModelConfig
    context_limit: int = Field(16384, ge=2048, le=65536)
    sources_file: str = "sources.yaml"


def load_config(path: Path | None = None) -> ReviewConfig | None:
    """Load the online-model config; ``None`` means "not configured"."""
    target = path or DEFAULT_CONFIG
    if not target.is_file():
        return None
    # Real DeepSeek values live in the workspace .env (git-ignored).
    load_env_file(target.parent.parent / ".env")
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {target}: {exc}") from exc
    # Real DeepSeek endpoint/model live in the local environment. The YAML
    # config only needs a provider shape and a non-secret fallback.
    model_data = data.get("model")
    if isinstance(model_data, dict):
        env_base = os.environ.get("DEEPSEEK_BASE_URL")
        env_model = os.environ.get("DEEPSEEK_MODEL")
        current_base = str(model_data.get("base_url") or "")
        if env_base or env_model:
            if "deepseek" in current_base.lower() or "deepseek" in (env_base or "").lower():
                if env_base:
                    model_data["base_url"] = env_base
                if env_model:
                    model_data["model"] = env_model
    try:
        return ReviewConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{target} does not match the review config: {exc}") from exc


def resolve_api_key(config: ReviewConfig) -> str | None:
    """Return the API key from the environment or the ignored local config."""
    from_env = os.environ.get(config.model.api_key_env, "").strip()
    if from_env:
        return from_env
    if config.model.api_key and config.model.api_key.strip():
        return config.model.api_key.strip()
    return None
