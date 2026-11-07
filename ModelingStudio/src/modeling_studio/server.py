"""Local model service access for ModelingStudio.

All calls go through ``shared.ai_runtime``: one cross-process lock, one server on
8080, and a server that is stopped only by the process that started it.
"""

from __future__ import annotations

from pathlib import Path

from ai_runtime import (
    FileLock,
    LockTimeout,
    ModelSpec,
    ServerBusy,
    ServerConfig,
    ServerStartError,
    is_healthy,
    model_ids,
    model_service,
    port_in_use,
    route_model,
)

from .config import WorkflowConfig

__all__ = [
    "ServerBusy",
    "ServerStartError",
    "LockTimeout",
    "is_healthy",
    "model_ids",
    "port_in_use",
    "managed_server",
    "managed_model",
    "probe",
]


def managed_server(config: WorkflowConfig, model_key: str, log_path: Path):
    """Ensure ``model_key`` is served on 8080 while holding the machine lock."""
    model: ModelSpec = config.model_spec(model_key)
    server: ServerConfig = config.server_config()
    lock = FileLock(
        config.runtime.lock_path_resolved,
        task_id=f"modeling:{model_key}",
        timeout_s=config.runtime.lock_timeout_s,
        stale_after_s=config.runtime.stale_after_s,
    )
    return model_service(server, model, lock, Path(log_path))


def probe(config: WorkflowConfig) -> dict:
    from ai_runtime import probe as runtime_probe

    payload = runtime_probe(config.server_config())
    lock = FileLock(config.runtime.lock_path_resolved)
    info = lock.read()
    payload["lock"] = info.to_dict() if info else None
    payload["lock_stale"] = lock.is_stale(info) if info else False
    return payload

def managed_model(config: WorkflowConfig, model_key: str, log_path: Path, *, vision: bool = False):
    """Yield a local route, or an explicit remote route when 8080 is unavailable.

    The caller must write ``route.provider`` and ``route.model`` into the task
    record and metadata; remote calls are never labelled as local.
    """
    model: ModelSpec = config.model_spec(model_key)
    server: ServerConfig = config.server_config()
    lock = FileLock(
        config.runtime.lock_path_resolved,
        task_id=f"modeling:{model_key}",
        timeout_s=config.runtime.lock_timeout_s,
        stale_after_s=config.runtime.stale_after_s,
    )
    return route_model(
        server,
        model,
        lock,
        Path(log_path),
        remote=config.remote.runtime(),
        vision=vision,
    )
