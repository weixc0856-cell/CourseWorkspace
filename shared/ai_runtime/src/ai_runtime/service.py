"""Local model service lifecycle on a single port (PRD FR-09).

The service is only manipulated while holding the cross-process lock. A process
stops only the server it started; a server owned by someone else is reused when
the alias matches, otherwise the caller gets ``ServerBusy``.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .locks import FileLock


class ServerBusy(RuntimeError):
    """8080 is serving another model, or is occupied but unhealthy."""


class ServerStartError(RuntimeError):
    pass


@dataclass
class ServerConfig:
    executable: str
    host: str = "127.0.0.1"
    port: int = 8080
    startup_timeout_s: int = 300
    stop_timeout_s: int = 30


@dataclass
class ModelSpec:
    key: str
    alias: str
    args: list[str] = field(default_factory=list)
    context: int = 16384


def _opener() -> urllib.request.OpenerDirector:
    # Ignore HTTP(S)_PROXY: the model server is always local.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_json(url: str, timeout: float) -> dict | None:
    try:
        with _opener().open(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def base_url(server: ServerConfig) -> str:
    return f"http://{server.host}:{server.port}"


def is_healthy(server: ServerConfig, timeout: float = 2.0) -> bool:
    payload = _get_json(f"{base_url(server)}/health", timeout)
    return bool(payload) and payload.get("status") == "ok"


def model_ids(server: ServerConfig, timeout: float = 5.0) -> list[str]:
    payload = _get_json(f"{base_url(server)}/v1/models", timeout) or {}
    return [str(item.get("id", "")) for item in payload.get("data", [])]


def port_in_use(server: ServerConfig) -> bool:
    try:
        with socket.create_connection((server.host, server.port), timeout=0.5):
            return True
    except OSError:
        return False


def probe(server: ServerConfig) -> dict:
    return {
        "base_url": base_url(server),
        "healthy": is_healthy(server),
        "port_in_use": port_in_use(server),
        "models": model_ids(server),
        "lock": None,
    }


def _wait_healthy(
    server: ServerConfig,
    process: subprocess.Popen | None,
    timeout_s: int,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_healthy(server):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(1.0)
    return False


def _wait_port_free(server: ServerConfig, timeout_s: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not port_in_use(server):
            return True
        time.sleep(0.5)
    return not port_in_use(server)


def _log_tail(path: Path, limit: int = 2000) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def _stop(process: subprocess.Popen, server: ServerConfig) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=server.stop_timeout_s)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    _wait_port_free(server)


@contextmanager
def model_service(
    server: ServerConfig,
    model: ModelSpec,
    lock: FileLock,
    log_path: Path,
):
    """Hold the machine-wide lock and ensure ``model.alias`` is served.

    Yields ``"reused"`` or ``"started"``. Stops the server only if this call
    started it. The lock is always released.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with lock:
        ids = model_ids(server) if is_healthy(server) else []
        if ids:
            if model.alias in ids:
                yield "reused"
                return
            raise ServerBusy(
                f"{server.port} is serving {ids}, but this task needs {model.alias}; "
                "refusing to stop another owner's server"
            )

        if port_in_use(server):
            if _wait_healthy(server, None, server.startup_timeout_s):
                ids = model_ids(server)
                if model.alias in ids:
                    yield "reused"
                    return
                raise ServerBusy(
                    f"{server.port} is serving {ids}, but this task needs {model.alias}; "
                    "refusing to stop another owner's server"
                )
            raise ServerBusy(f"port {server.port} is occupied but the service is not healthy")

        executable = str(Path(server.executable))
        if not Path(executable).is_file():
            raise ServerStartError(f"model executable not found: {executable}")

        header = (
            f"\n# {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"model={model.key} alias={model.alias}\n"
            f"# {executable} {' '.join(model.args)}\n"
        )
        with log_path.open("a", encoding="utf-8") as log:
            log.write(header)
            log.flush()
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(
                [executable, *model.args],
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        try:
            if not _wait_healthy(server, process, server.startup_timeout_s):
                raise ServerStartError(
                    f"llama-server for {model.alias} did not become healthy; "
                    f"log: {log_path}\n{_log_tail(log_path)}"
                )
            ids = model_ids(server)
            if model.alias not in ids:
                raise ServerStartError(
                    f"server is healthy but {model.alias} is not listed; got {ids}"
                )
            yield "started"
        finally:
            _stop(process, server)
