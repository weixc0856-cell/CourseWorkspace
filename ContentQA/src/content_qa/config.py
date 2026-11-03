from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {target}: {exc}") from exc
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
