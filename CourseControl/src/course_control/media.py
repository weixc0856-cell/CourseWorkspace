"""Media primitives shared by the V1 timeline, the adapter layer and E6.

These functions were originally written inside the E6 adapter.  They are
generic (hash, probe, timestamp, asset reference, SRT) and the V1 main path
depends on them, so they live here rather than in a module named "legacy".
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .contracts_v1 import AssetRef
from .paths import path_problem


class MediaError(RuntimeError):
    """Raised when media or a manifest cannot be read safely."""


@dataclass(frozen=True)
class MediaStream:
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    r_frame_rate: str | None = None
    avg_frame_rate: str | None = None
    duration_s: float | None = None
    nb_frames: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(frozen=True)
class MediaProbe:
    path: Path
    duration_s: float | None
    size: int | None
    streams: tuple[MediaStream, ...]

    def first(self, codec_type: str) -> MediaStream | None:
        return next((item for item in self.streams if item.codec_type == codec_type), None)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise MediaError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def seconds_to_ms(value: float | int) -> int:
    """Legacy seconds -> integer milliseconds, half up, via Decimal."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MediaError(f"duration must be a number, got {value!r}")
    if value < 0:
        raise MediaError(f"duration must be non-negative, got {value!r}")
    return int(
        (Decimal(str(value)) * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _resolve(base: Path, relative: str) -> Path:
    problem = path_problem(relative)
    if problem:
        raise MediaError(f"invalid manifest path {relative!r}: {problem}")
    return (base / relative).resolve()


def asset_ref(path: Path, workspace: Path, kind: str, origin: str = "rendered") -> AssetRef:
    resolved = path.resolve()
    root = workspace.resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
        origin_value = origin
    except ValueError:
        relative = str(resolved)
        origin_value = "external"
    if not resolved.is_file():
        raise MediaError(f"asset not found: {resolved}")
    return AssetRef(
        path=relative,
        sha256=sha256_file(resolved),
        bytes=resolved.stat().st_size,
        kind=kind,
        origin=origin_value,
        version=None,
    )


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_stream(raw: dict) -> MediaStream:
    return MediaStream(
        codec_type=str(raw.get("codec_type", "")),
        codec_name=raw.get("codec_name"),
        width=_optional_int(raw.get("width")),
        height=_optional_int(raw.get("height")),
        r_frame_rate=raw.get("r_frame_rate"),
        avg_frame_rate=raw.get("avg_frame_rate"),
        duration_s=_optional_float(raw.get("duration")),
        nb_frames=_optional_int(raw.get("nb_frames")),
        sample_rate=_optional_int(raw.get("sample_rate")),
        channels=_optional_int(raw.get("channels")),
    )


def probe_media(path: Path) -> MediaProbe:
    """Run ffprobe and return only the fields the adapter checks."""

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        (
            "format=duration,size:"
            "stream=index,codec_type,codec_name,width,height,"
            "r_frame_rate,avg_frame_rate,duration,nb_frames,sample_rate,channels"
        ),
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError(f"ffprobe could not run for {path}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise MediaError(f"ffprobe failed for {path}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError(f"ffprobe returned invalid JSON for {path}: {exc}") from exc
    fmt = payload.get("format", {})
    return MediaProbe(
        path=path,
        duration_s=_optional_float(fmt.get("duration")),
        size=_optional_int(fmt.get("size")),
        streams=tuple(_parse_stream(raw) for raw in payload.get("streams", [])),
    )


def ffprobe_version() -> str:
    try:
        result = subprocess.run(
            ["ffprobe", "-version"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    first = (result.stdout or "").splitlines()
    return first[0] if first else "unknown"


def parse_rate(value: str | None) -> tuple[int, int] | None:
    if not value or value == "0/0":
        return None
    match = re.match(r"^(\d+)/(\d+)$", value)
    if not match:
        return None
    num, den = int(match.group(1)), int(match.group(2))
    if num <= 0 or den <= 0:
        return None
    return num, den
