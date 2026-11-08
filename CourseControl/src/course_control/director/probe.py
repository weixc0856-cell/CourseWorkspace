"""Measure already-rendered animation inserts so the plan knows page vs asset length."""
from __future__ import annotations

from pathlib import Path

from ..paths import LessonPaths
from ..utils import probe_media
from .schema import ShotPlan

PROBE_GLOBS = (
    "director/probe/media/videos/**/{name}.mp4",
    "tmp/manim-media/videos/**/{name}.mp4",
    "media/videos/**/{name}.mp4",
)


def probe_asset_seconds(paths: LessonPaths, shots: list[ShotPlan]) -> dict[str, float]:
    measured: dict[str, float] = {}
    for shot in shots:
        if not shot.scene or shot.engine != "manim" or "::" not in shot.scene:
            continue
        name = shot.scene.split("::", 1)[1]
        candidates: list[Path] = []
        animation = paths.build_root / "animation" / f"{Path(shot.scene.split('::')[0]).stem}.mp4"
        if animation.is_file():
            candidates.append(animation)
        for pattern in PROBE_GLOBS:
            candidates.extend(paths.build_root.glob(pattern.format(name=name)))
        if not candidates:
            continue
        newest = max(candidates, key=lambda item: item.stat().st_mtime)
        try:
            info = probe_media(newest)
        except Exception:  # noqa: BLE001 - a broken probe must not block planning
            continue
        if info.duration:
            measured[shot.id] = round(float(info.duration), 3)
    return measured
