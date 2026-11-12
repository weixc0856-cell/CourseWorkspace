"""VoxCPM2 narration client, cache and service lifecycle (V1)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

import yaml

from .session import normalize_stream, sha256_text
from .workspace_layout import runtime_root

DEFAULT_PORT = 50000
DEFAULT_TIMEOUT_S = 900


class TtsError(RuntimeError):
    pass


class TtsUnavailable(TtsError):
    pass


class TtsBusy(TtsError):
    pass


class TtsTimeout(TtsError):
    pass


def _opener() -> urllib.request.OpenerDirector:
    # Local services must never go through the system proxy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_json(url: str, timeout: float) -> dict | None:
    try:
        with _opener().open(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def health(base_url: str, timeout: float = 2.0) -> dict | None:
    return _get_json(base_url.rstrip("/") + "/health", timeout)


def load_local_paths(workspace: Path) -> dict:
    path = workspace / "config" / "local-paths.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def port_owner(port: int) -> dict | None:
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() not in {"TCP", "TCPV6"}:
            continue
        if not parts[1].endswith(f":{port}") or parts[-2].upper() != "LISTENING":
            continue
        pid = parts[-1]
        name = ""
        try:
            task = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if task.stdout.strip():
                name = task.stdout.split('","')[0].strip('"')
        except (OSError, subprocess.TimeoutExpired):
            pass
        return {"pid": int(pid), "process": name}
    return None


def segment_cache_key(
    text: str,
    voice_ref: Path,
    prompt_text: str,
    *,
    mode: str = "prompt_reference",
    style: str | None = None,
    speed: float = 1.0,
    timesteps: int = 10,
    cfg: float = 2.0,
    text_frontend: bool = True,
    voice_bible_sha256: str | None = None,
    lexicon_hits: Sequence[tuple[str, str]] = (),
) -> str:
    payload = {
        "text": normalize_stream(text),
        "voice_ref": sha256_text(_hash_file(voice_ref)),
        "prompt_text": prompt_text,
        "mode": mode,
        "style": style,
        "model": "VoxCPM2",
        "timesteps": timesteps,
        "cfg": cfg,
        "speed": speed,
        "text_frontend": text_frontend,
    }
    # Only present when a lesson opts into voice assets, so every key produced
    # before this existed stays valid.
    if voice_bible_sha256:
        payload["voice_bible_sha256"] = voice_bible_sha256
    if lexicon_hits:
        payload["lexicon_hits"] = [[term, say] for term, say in lexicon_hits]
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def synthesize(
    base_url: str,
    text: str,
    voice_ref: Path,
    prompt_text: str | None,
    output: Path,
    *,
    speed: float = 1.0,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    mode: str = "prompt_reference",
    reference_wav: Path | None = None,
    style: str | None = None,
    text_frontend: bool = True,
) -> dict:
    if not text.strip():
        raise TtsError("text must not be blank")
    if not voice_ref.is_file():
        raise TtsError(f"voice reference not found: {voice_ref}")
    reference_path = reference_wav or voice_ref
    if not reference_path.is_file():
        raise TtsError(f"reference audio not found: {reference_path}")
    style_applied = bool(style and mode == "reference_only")
    spoken = f"{style} {text}".strip() if style_applied else text
    if mode == "reference_only":
        payload = {
            "text": spoken,
            "reference_wav": str(reference_path.resolve()),
            "speed": speed,
            "text_frontend": text_frontend,
        }
    elif mode == "prompt_reference":
        payload = {
            "text": spoken,
            "prompt_wav": str(voice_ref.resolve()),
            "prompt_text": prompt_text or "",
            "reference_wav": str(reference_path.resolve()),
            "speed": speed,
            "text_frontend": text_frontend,
        }
    else:
        raise TtsError(f"unsupported narration mode: {mode}")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/tts",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _opener().open(request, timeout=timeout_s) as response:
            audio = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise TtsError(f"TTS HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TtsUnavailable(f"TTS request failed: {exc}") from exc
    if len(audio) < 44:
        raise TtsError("TTS returned empty audio")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_bytes(audio)
    temp.replace(output)
    return {
        "bytes": len(audio),
        "audio_seconds": float(headers.get("x-audio-seconds") or 0.0),
        "synth_seconds": float(headers.get("x-synth-seconds") or 0.0),
        "sample_rate": int(headers.get("x-sample-rate") or 0),
        "prompt_mode": headers.get("x-prompt-mode"),
        "text_normalize": headers.get("x-text-normalize"),
        "speed_stretch": headers.get("x-speed-stretch"),
        "mode": mode,
        "style": style if style_applied else None,
        "style_applied": style_applied,
    }


class TtsService:
    """Hold the 50000 lock, reuse or start the runtime, and report the owner."""

    def __init__(
        self,
        workspace: Path,
        *,
        ai_root: Path,
        runtime_dir: Path,
        log_path: Path,
        start_service: bool = True,
        wait_timeout_s: int = 1800,
        port: int = DEFAULT_PORT,
    ):
        self.workspace = workspace
        self.ai_root = ai_root
        self.runtime_dir = runtime_dir
        self.log_path = log_path
        self.start_service = start_service
        self.wait_timeout_s = wait_timeout_s
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self.lock_path = runtime_root(workspace) / "locks" / f"tts-{port}.lock"
        self._lock = None
        self._process: subprocess.Popen | None = None
        self._started = False
        self.mode = "reused"

    def _acquire(self) -> None:
        from ai_runtime.locks import FileLock, LockTimeout

        lock = FileLock(
            self.lock_path,
            task_id=f"course:narrate:{os.getpid()}",
            timeout_s=self.wait_timeout_s,
            stale_after_s=max(3600.0, self.wait_timeout_s * 2),
        )
        deadline = time.monotonic() + self.wait_timeout_s
        while True:
            info = lock.read()
            if info is None:
                break
            if time.monotonic() >= deadline:
                raise TtsBusy(
                    f"TTS {self.port} busy: task={info.task_id} pid={info.pid} "
                    f"since={info.created_at}"
                )
            print(
                f"TTS {self.port} busy: task={info.task_id} pid={info.pid} "
                f"since={info.created_at}; waiting",
                flush=True,
            )
            time.sleep(10.0)
        try:
            lock.acquire()
        except LockTimeout as exc:
            raise TtsBusy(str(exc)) from exc
        self._lock = lock

    def _wait_ready(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            payload = health(self.base_url)
            if payload and payload.get("status") == "ready":
                return True
            if self._process is not None and self._process.poll() is not None:
                return False
            time.sleep(1.0)
        return False

    def _start(self) -> None:
        python = self.runtime_dir / ".venv" / "Scripts" / "python.exe"
        if not python.is_file():
            python = self.runtime_dir / "venv" / "Scripts" / "python.exe"
        script = self.runtime_dir / "api_server.py"
        if not python.is_file() or not script.is_file():
            raise TtsUnavailable(f"VoxCPM runtime not found: {self.runtime_dir}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "VOX_MODEL_DIR": str(self.ai_root / "models" / "voxcpm2"),
                "VOX_DEVICE": "cpu",
                "VOX_CPU_THREADS": "12",
                "VOX_TIMESTEPS": "10",
                "VOX_CFG": "2.0",
                "VOX_HOST": "127.0.0.1",
                "VOX_PORT": str(self.port),
            }
        )
        log = self.log_path.open("a", encoding="utf-8")
        self._process = subprocess.Popen(
            [str(python), str(script)],
            cwd=str(self.runtime_dir),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if not self._wait_ready(120.0):
            self._stop()
            raise TtsUnavailable(
                f"VoxCPM did not become ready; see {self.log_path}"
            )
        self._started = True
        self.mode = "started"

    def _stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10)
        self._process = None

    def __enter__(self) -> "TtsService":
        self._acquire()
        try:
            payload = health(self.base_url)
            if payload and payload.get("status") == "ready":
                self.mode = "reused"
                return self
            if payload and payload.get("status") == "loading":
                if not self._wait_ready(120.0):
                    raise TtsUnavailable("VoxCPM is loading but did not become ready")
                self.mode = "reused"
                return self
            if not self.start_service:
                raise TtsUnavailable(f"TTS {self.port} is not running")
            self._start()
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._started:
            self._stop()
        if self._lock is not None:
            self._lock.release()
            self._lock = None

    def status(self) -> dict:
        info = None
        if self._lock is not None:
            info = self._lock.read()
        return {
            "health": health(self.base_url),
            "port_owner": port_owner(self.port),
            "lock": info.to_dict() if info else None,
            "mode": self.mode,
            "log": str(self.log_path),
        }
