"""Animatic timeline: the playable units an animatic is built from.

An animatic is a decision tool, not a render.  Every unit is one still or one
already-rendered clip, played against the lesson's real narration so the edit
can be judged before any costly rendering is committed.

Timing authority, in order:

1. ``build/<slug>/timeline/page-plan.json`` -- per-page start and duration,
   measured from narration when available.
2. ``build/<slug>/shots.json`` base shots -- the normalised timeline.
3. ``build/<slug>/scenes/manifest.json`` -- per-page clips, cumulative timing.

The visual for a unit is chosen independently of its timing: a rendered page
clip beats a still, a still beats a placeholder.  Units carry absolute times;
the builder turns those into a frame grid so rounding never accumulates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..paths import LessonPaths

FPS = 30
DEFAULT_SIZE = (854, 480)

# A gap shorter than this is rounding noise, not a hole in the timeline.
GAP_EPSILON_S = 0.02


class AnimaticError(RuntimeError):
    """The lesson has no timeline to preview yet."""


@dataclass
class Unit:
    id: str
    kind: str  # "still" | "clip" | "placeholder"
    source: Path | None
    source_rel: str
    start_s: float
    duration_s: float
    label: str
    slide: int | None = None

    @property
    def end_s(self) -> float:
        return self.start_s + self.duration_s

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source_rel,
            "start_s": round(self.start_s, 3),
            "duration_s": round(self.duration_s, 3),
            "label": self.label,
            "slide": self.slide,
        }


@dataclass
class Timeline:
    mode: str
    units: list[Unit]
    fps: int = FPS
    width: int = DEFAULT_SIZE[0]
    height: int = DEFAULT_SIZE[1]
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []

    @property
    def duration_s(self) -> float:
        return self.units[-1].end_s if self.units else 0.0

    def frames(self) -> list[int]:
        """Frames per unit on one absolute grid; the sum is the video length."""
        counts = []
        for unit in self.units:
            start = round(unit.start_s * self.fps)
            end = round(unit.end_s * self.fps)
            counts.append(max(1, end - start))
        return counts

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "mode": self.mode,
            "fps": self.fps,
            "size": [self.width, self.height],
            "duration_s": round(self.duration_s, 3),
            "units": [unit.as_dict() for unit in self.units],
            "warnings": list(self.warnings),
        }


def resolve(paths: LessonPaths, *, fps: int = FPS, size: tuple[int, int] = DEFAULT_SIZE) -> Timeline:
    """Pick the timeline and the visuals for one lesson."""
    return resolve_build(paths.build_root, slug=paths.slug, fps=fps, size=size)


def resolve_build(
    build: Path,
    *,
    slug: str | None = None,
    fps: int = FPS,
    size: tuple[int, int] = DEFAULT_SIZE,
) -> Timeline:
    """Resolve the timeline straight from a build directory."""
    build = Path(build)
    slug = slug or build.name
    warnings: list[str] = []
    pages = _read_json(build / "timeline" / "page-plan.json")
    if pages and pages.get("pages"):
        units = _page_units(build, pages["pages"], warnings)
        mode = "pages"
    else:
        shots = _read_json(build / "shots.json")
        if shots and shots.get("shots"):
            units = _shot_units(build, shots["shots"], warnings)
            mode = "shots"
        else:
            manifest = _read_json(build / "scenes" / "manifest.json")
            if not (manifest and manifest.get("pages")):
                raise AnimaticError(
                    f"no timeline for {slug}: run `course-control build` or `collect` first "
                    f"(looked for timeline/page-plan.json, shots.json, scenes/manifest.json under {build})"
                )
            units = _manifest_units(build, manifest["pages"], warnings)
            mode = "scenes"
    if not units:
        raise AnimaticError(f"no playable units for {slug}")
    units = _fill_gaps(units, warnings)
    return Timeline(mode=mode, units=units, fps=fps, width=size[0], height=size[1], warnings=warnings)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _page_source(build: Path, slide: int) -> tuple[str, Path | None, str]:
    clip = Path("scenes") / "pages" / f"page-{slide:03d}.mp4"
    if (build / clip).is_file():
        return "clip", (build / clip).resolve(), clip.as_posix()
    still = Path("slides") / f"slide-{slide:03d}.png"
    if (build / still).is_file():
        return "still", (build / still).resolve(), still.as_posix()
    return "placeholder", None, ""


def _page_units(build: Path, pages: list[dict], warnings: list[str]) -> list[Unit]:
    units: list[Unit] = []
    for page in pages:
        slide = int(page.get("slide") or len(units) + 1)
        start = float(page.get("start_s") or 0.0)
        duration = float(page.get("duration_s") or 0.0)
        if duration <= 0:
            warnings.append(f"page {slide}: non-positive duration, skipped")
            continue
        kind, source, rel = _page_source(build, slide)
        if kind == "placeholder":
            warnings.append(f"page {slide}: no page clip and no slide still")
        units.append(
            Unit(
                id=f"page-{slide:03d}",
                kind=kind,
                source=source,
                source_rel=rel,
                start_s=start,
                duration_s=duration,
                label=f"P{slide:02d}",
                slide=slide,
            )
        )
    return units


def _manifest_units(build: Path, pages: list[dict], warnings: list[str]) -> list[Unit]:
    units: list[Unit] = []
    cursor = 0.0
    for page in pages:
        slide = int(page.get("slide") or len(units) + 1)
        duration = float(page.get("duration_s") or 0.0)
        if duration <= 0:
            continue
        rel = Path(str(page.get("file") or ""))
        source = (build / rel).resolve() if str(rel) else None
        if source is None or not source.is_file():
            kind, source, rel_posix = _page_source(build, slide)
            if kind == "placeholder":
                warnings.append(f"page {slide}: listed clip is missing")
        else:
            kind, rel_posix = "clip", rel.as_posix()
        units.append(
            Unit(
                id=f"page-{slide:03d}",
                kind=kind,
                source=source,
                source_rel=rel_posix,
                start_s=cursor,
                duration_s=duration,
                label=f"P{slide:02d}",
                slide=slide,
            )
        )
        cursor += duration
    return units


def _shot_units(build: Path, shots: list[dict], warnings: list[str]) -> list[Unit]:
    units: list[Unit] = []
    overlays = 0
    for shot in shots:
        if shot.get("timeline_role") != "base":
            overlays += 1
            continue
        duration = float(shot.get("duration_s") or 0.0)
        if duration <= 0:
            continue
        shot_id = str(shot.get("id") or f"unit-{len(units) + 1}")
        rel = Path(str(shot.get("source") or ""))
        source = (build / rel).resolve() if str(rel) else None
        kind = "clip" if shot.get("kind") in {"animation", "recording"} else "still"
        if source is None or not source.is_file():
            slide = shot.get("slide")
            if slide:
                fallback_kind, fallback, fallback_rel = _page_source(build, int(slide))
                warnings.append(f"{shot_id}: {rel.as_posix() or 'source'} is missing, using {fallback_kind}")
                kind, source, rel = fallback_kind, fallback, Path(fallback_rel) if fallback_rel else rel
            else:
                kind, source = "placeholder", None
                warnings.append(f"{shot_id}: no source and no slide to fall back on")
        units.append(
            Unit(
                id=shot_id,
                kind=kind,
                source=source,
                source_rel=rel.as_posix() if str(rel) else "",
                start_s=float(shot.get("start_s") or 0.0),
                duration_s=duration,
                label=shot_id,
                slide=shot.get("slide"),
            )
        )
    if overlays:
        warnings.append(f"{overlays} overlay shot(s) not composited into the animatic")
    units.sort(key=lambda unit: unit.start_s)
    return units


def _fill_gaps(units: list[Unit], warnings: list[str]) -> list[Unit]:
    """Insert placeholders so the concatenation keeps absolute timing."""
    filled: list[Unit] = []
    cursor = 0.0
    for unit in units:
        gap = unit.start_s - cursor
        if gap > GAP_EPSILON_S:
            warnings.append(f"gap {gap:.2f}s before {unit.id} filled with a placeholder")
            filled.append(
                Unit(
                    id=f"gap-{len(filled) + 1:03d}",
                    kind="placeholder",
                    source=None,
                    source_rel="",
                    start_s=cursor,
                    duration_s=gap,
                    label="GAP",
                )
            )
        filled.append(unit)
        cursor = max(cursor, unit.end_s)
    return filled
