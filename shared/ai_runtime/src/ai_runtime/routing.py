"""Local-first model routing with an explicit remote fallback.

The local llama.cpp service on 8080 is always tried first. Only when the
caller configures a remote provider and the local service reports a matching
fallback reason (busy, start error, lock timeout, missing executable) does the
route switch to the remote endpoint. The route is returned to the caller so it
can be written into the task record; a remote call is never reported as local.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from .locks import FileLock, LockTimeout
from .remote import RemoteConfig, RemoteUnavailable
from .service import (
    ModelSpec,
    ServerBusy,
    ServerConfig,
    ServerStartError,
    base_url,
    model_service,
)


@dataclass
class ModelRoute:
    provider: str
    base_url: str
    api_key: str
    model: str
    mode: str
    context_limit: int | None = None
    vision: bool = False
    trust_env: bool = False


def _fallback_reason(exc: BaseException) -> str:
    if isinstance(exc, ServerBusy):
        return "busy"
    if isinstance(exc, ServerStartError):
        return "start_error"
    if isinstance(exc, LockTimeout):
        return "lock_timeout"
    return type(exc).__name__


def _local_route(server: ServerConfig, model: ModelSpec, mode: str, vision: bool) -> ModelRoute:
    return ModelRoute(
        provider="local",
        base_url=base_url(server).rstrip("/") + "/v1",
        api_key="sk-local",
        model=model.alias,
        mode=mode,
        context_limit=model.context,
        vision=vision,
        trust_env=False,
    )


@contextmanager
def route_model(
    server: ServerConfig,
    model: ModelSpec,
    lock: FileLock,
    log_path,
    *,
    remote: RemoteConfig | None = None,
    vision: bool = False,
    fallback_on: tuple[str, ...] | None = None,
):
    """Yield a :class:`ModelRoute` for the local service or a remote fallback.

    The local lock is released before a remote call is made, so an occupied
    8080 does not block the fallback. A remote route is only produced when the
    remote provider is enabled, has a key, supports the requested modality, and
    the local failure reason is explicitly allowed.
    """
    try:
        with model_service(server, model, lock, log_path) as mode:
            yield _local_route(server, model, mode, vision)
            return
    except (ServerBusy, ServerStartError, LockTimeout) as exc:
        reason = _fallback_reason(exc)
        allowed = fallback_on
        if allowed is None and remote is not None:
            allowed = remote.fallback_on
        if (
            remote is not None
            and reason in (allowed or ())
            and remote.available(vision=vision)
        ):
            key = remote.resolved_key()
            if key is None:
                raise
            yield ModelRoute(
                provider="remote",
                base_url=remote.base_url.rstrip("/"),
                api_key=key,
                model=remote.model_for(vision=vision),
                mode="remote",
                context_limit=None,
                vision=vision,
                trust_env=remote.trust_env,
            )
            return
        raise


__all__ = ["ModelRoute", "route_model", "RemoteUnavailable"]
