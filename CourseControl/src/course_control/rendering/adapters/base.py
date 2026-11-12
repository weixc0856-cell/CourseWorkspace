from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from course_control.content.contracts import Status
from course_control.platform.utils import MediaInfo, probe_media


def selected(paths, shot_id: str) -> bool:
    """Shot filter for partial renders; mocks without the method select all."""
    checker = getattr(paths, "selects", None)
    return checker(shot_id) if checker is not None else True


def verify_media(
    path: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    expected_duration_s: float | None = None,
    duration_tolerance: float = 0.25,
) -> tuple[MediaInfo, list[str]]:
    """Shared per-shot media contract for every renderer.

    Raises ``ValueError`` on hard mismatches (unreadable, resolution, fps,
    duration outside tolerance). Returns non-fatal warnings for duration drift.
    """
    info = probe_media(path)
    if width is not None and height is not None:
        if info.width != width or info.height != height:
            raise ValueError(
                f"resolution {info.width}x{info.height} does not match {width}x{height}"
            )
    if fps is not None:
        if info.fps is None or abs(info.fps - fps) > 0.01:
            raise ValueError(f"fps {info.fps} does not match {fps}")
    if info.duration is None or info.duration <= 0:
        raise ValueError("duration is missing or zero")
    warnings: list[str] = []
    if expected_duration_s:
        delta = abs(info.duration - expected_duration_s)
        limit = max(1.0, expected_duration_s * duration_tolerance)
        if delta > limit:
            raise ValueError(
                f"duration {info.duration:.2f}s differs from expected "
                f"{expected_duration_s:.2f}s by more than {limit:.2f}s"
            )
        if delta > max(0.5, expected_duration_s * 0.10):
            warnings.append(
                f"duration {info.duration:.2f}s differs from expected "
                f"{expected_duration_s:.2f}s"
            )
    return info, warnings


@dataclass
class StageOutcome:
    name: str
    status: Status
    outputs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reason: str | None = None
    duration_ms: int = 0
