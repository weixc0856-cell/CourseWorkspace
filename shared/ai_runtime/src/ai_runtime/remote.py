"""Remote OpenAI-compatible model provider (fallback for local 8080).

The local llama.cpp service remains the first choice. This module only
describes a remote endpoint and performs a single chat completion; routing
decisions live in :mod:`ai_runtime.routing`.

Secrets are read from the environment by name. The key is never written to
task records, logs, exceptions, or returned payloads.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class RemoteError(RuntimeError):
    """Base class for remote-provider failures."""


class RemoteUnavailable(RemoteError):
    """The remote provider is disabled, unconfigured, or unreachable."""


class RemoteAuthError(RemoteError):
    """The remote provider rejected the configured credential."""


class RemoteResponseError(RemoteError):
    """The remote provider returned a non-retryable error."""


@dataclass
class RemoteConfig:
    enabled: bool = False
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-flash"
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key: str | None = None
    timeout_s: int = 120
    max_tokens: int = 4096
    temperature: float = 0.1
    supports_vision: bool = True
    vision_model: str | None = "deepseek-flash"
    trust_env: bool = True
    fallback_on: tuple[str, ...] = (
        "busy",
        "start_error",
        "lock_timeout",
        "missing_executable",
    )

    def __post_init__(self) -> None:
        # Environment is authoritative. Generic REMOTE_* names describe any
        # OpenAI-compatible provider; DeepSeek-specific names remain aliases.
        # The tracked config/example files only contain safe defaults.
        generic = (
            ("enabled", "REMOTE_ENABLED"),
            ("provider", "REMOTE_PROVIDER"),
            ("base_url", "REMOTE_BASE_URL"),
            ("model", "REMOTE_MODEL"),
            ("vision_model", "REMOTE_VISION_MODEL"),
            ("api_key_env", "REMOTE_API_KEY_ENV"),
        )
        from_generic: set[str] = set()
        for attr, env_name in generic:
            value = os.environ.get(env_name)
            if value is None:
                continue
            from_generic.add(attr)
            if attr == "enabled":
                self.enabled = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                setattr(self, attr, value)
        if self.provider == "deepseek":
            for attr, env_name in (
                ("base_url", "DEEPSEEK_BASE_URL"),
                ("model", "DEEPSEEK_MODEL"),
                ("vision_model", "DEEPSEEK_VISION_MODEL"),
            ):
                if attr in from_generic:
                    continue
                value = os.environ.get(env_name)
                if value:
                    setattr(self, attr, value)
        # Project policy: DeepSeek calls are pinned to deepseek-flash.
        # deepseek-v4-pro and other DeepSeek models are disabled. Other
        # OpenAI-compatible providers may use their configured models.
        if self.provider != "deepseek":
            return
        for label, value in (("model", self.model), ("vision_model", self.vision_model)):
            if value and value != "deepseek-flash":
                raise ValueError(
                    f"DeepSeek is pinned to deepseek-flash; {label}={value!r} is disabled"
                )

    def resolved_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        names = [self.api_key_env]
        if self.provider == "deepseek" and self.api_key_env in {
            "DEEPSEEK_API_KEY",
            "DeepSeek-API",
        }:
            # Accept the existing Windows variable name as an alias, but only
            # for the documented DeepSeek key names. A custom name is exact.
            names.extend(["DEEPSEEK_API_KEY", "DeepSeek-API"])
        for name in names:
            value = os.environ.get(name)
            if value:
                return value
        return None

    def model_for(self, *, vision: bool = False) -> str:
        if vision:
            if not self.supports_vision or not self.vision_model:
                raise RemoteUnavailable(
                    f"{self.provider} remote fallback has no vision model configured"
                )
            return self.vision_model
        return self.model

    def available(self, *, vision: bool = False) -> bool:
        if not self.enabled or not self.resolved_key():
            return False
        if vision and not (self.supports_vision and self.vision_model):
            return False
        return True

    def endpoint(self, path: str) -> str:
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")


@dataclass
class RemoteResult:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str | None = None


def _opener(config: RemoteConfig) -> urllib.request.OpenerDirector:
    if config.trust_env:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _request(
    config: RemoteConfig,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout_s: int | None = None,
) -> dict:
    key = config.resolved_key()
    if not key:
        raise RemoteUnavailable(
            f"remote provider {config.provider} has no key in {config.api_key_env}"
        )
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        config.endpoint(path), data=data, headers=headers, method=method
    )
    try:
        with _opener(config).open(request, timeout=timeout_s or config.timeout_s) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code in (401, 403):
            raise RemoteAuthError(
                f"remote provider {config.provider} rejected the credential "
                f"(HTTP {exc.code})"
            ) from exc
        if exc.code in (408, 409, 429) or exc.code >= 500:
            raise RemoteUnavailable(
                f"remote provider {config.provider} is unavailable "
                f"(HTTP {exc.code}): {body}"
            ) from exc
        raise RemoteResponseError(
            f"remote provider {config.provider} returned HTTP {exc.code}: {body}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RemoteUnavailable(
            f"remote provider {config.provider} is unreachable: {exc}"
        ) from exc


def health(config: RemoteConfig, timeout_s: int = 5) -> dict:
    """Return a small, secret-free health payload for diagnostics."""
    key_present = bool(config.resolved_key())
    payload = {
        "provider": config.provider,
        "enabled": config.enabled,
        "base_url": config.base_url,
        "model": config.model,
        "key_present": key_present,
        "vision_model": config.vision_model,
    }
    if not config.enabled or not key_present:
        payload["reachable"] = False
        return payload
    try:
        _request(config, "GET", "models", timeout_s=timeout_s)
        payload["reachable"] = True
    except RemoteError as exc:
        payload["reachable"] = False
        payload["error"] = str(exc)
    return payload


def chat_completion(
    config: RemoteConfig,
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    json_object: bool = False,
    timeout_s: int | None = None,
    vision: bool = False,
) -> RemoteResult:
    """Perform one OpenAI-compatible chat completion.

    ``vision`` selects the configured vision model and must be explicitly
    enabled; otherwise a remote text model is never asked to read images.
    """
    if not config.enabled:
        raise RemoteUnavailable(f"remote provider {config.provider} is disabled")
    selected = model or config.model_for(vision=vision)
    payload: dict = {
        "model": selected,
        "messages": messages,
        "max_tokens": max_tokens or config.max_tokens,
        "temperature": config.temperature if temperature is None else temperature,
    }
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    data = _request(config, "POST", "chat/completions", payload, timeout_s)
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RemoteResponseError(
            f"unexpected {config.provider} chat payload: {str(data)[:500]}"
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise RemoteResponseError(f"{config.provider} returned an empty chat completion")
    usage = dict(data.get("usage") or {})
    finish = choice.get("finish_reason")
    if finish is not None:
        usage["finish_reason"] = finish
    return RemoteResult(
        content=content,
        model=str(data.get("model") or selected),
        usage=usage,
        finish_reason=finish,
    )
