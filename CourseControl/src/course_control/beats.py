"""Director beat sheet: the authored, machine-checkable plan of a film.

A beat sheet lives next to the lesson (``lessons/<slug>/authoring/beats.yaml``)
and is validated against the measured narration.  It turns the "director layer"
from prose into a contract:

* every narration segment is covered exactly once, without gaps or overlaps;
* every shot is 5-16 s, carries at least two argument beats, and never leaves
  more than 4 s without a visual change;
* shots declare their long-lived objects (3B1B-style continuity): at least half
  of the film must keep an object alive across the shot;
* camera moves are allowed only with a written motive;
* the palette exists and passes the accessibility gates;
* a subtitled band at the bottom is reserved for burned captions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import yaml

from pydantic import Field, model_validator

from .contracts import StrictModel

BeatKind = Literal["reveal", "transform", "highlight", "flow", "camera", "annotation", "compare", "connect"]
Engine = Literal["manim", "motion_canvas", "blender", "code_video", "remotion"]

MAX_SHOT_SECONDS = 16.0
MIN_SHOT_SECONDS = 5.0
MAX_GAP_SECONDS = 4.0
MIN_LONG_LIVED_RATIO = 0.5


class Beat(StrictModel):
    at: float = Field(ge=0.0, le=1.0)
    kind: BeatKind
    action: str = Field(min_length=4)


class CameraMove(StrictModel):
    at: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=6.0, le=14.3)
    motive: str = Field(min_length=8)


class BeatShot(StrictModel):
    id: str = Field(min_length=1)
    segment: int = Field(ge=1)
    start: float = Field(ge=0.0, le=1.0)
    end: float = Field(gt=0.0, le=1.0)
    engine: Engine
    long_lived: list[str] = Field(default_factory=list)
    beats: list[Beat] = Field(min_length=2)
    camera: list[CameraMove] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end <= self.start:
            raise ValueError(f"{self.id}: end must be greater than start")
        if [beat.at for beat in self.beats] != sorted(beat.at for beat in self.beats):
            raise ValueError(f"{self.id}: beats must be ordered by 'at'")
        if [move.at for move in self.camera] != sorted(move.at for move in self.camera):
            raise ValueError(f"{self.id}: camera moves must be ordered by 'at'")
        return self


class BeatSheet(StrictModel):
    schema_version: int = 1
    lesson: str = Field(min_length=1)
    palette: str = "editorial"
    subtitle_safe_below: float = Field(le=-1.5)
    shots: list[BeatShot] = Field(min_length=1)


def _segment_durations(segments: list[tuple[float, float]]) -> list[float]:
    return [float(duration) for _, duration in segments]


def validate_sheet(
    sheet: BeatSheet,
    segments: list[tuple[float, float]],
    *,
    palette_ok: bool = True,
) -> list[str]:
    """Return a list of gate violations; empty means the sheet is shippable."""
    issues: list[str] = []
    if not palette_ok:
        issues.append("palette: accessibility gates failed")
    if not sheet.subtitle_safe_below <= -1.5:
        issues.append("subtitle band: subtitle_safe_below must be <= -1.5")

    durations = _segment_durations(segments)
    if len(durations) != len(segments):
        return issues + ["narration: no measured segments"]

    ids = [shot.id for shot in sheet.shots]
    duplicates = sorted({shot_id for shot_id in ids if ids.count(shot_id) > 1})
    if duplicates:
        issues.append(f"shots: duplicate ids {duplicates}")

    for segment_index, duration in enumerate(durations, start=1):
        shot_list = sorted(
            (shot for shot in sheet.shots if shot.segment == segment_index),
            key=lambda shot: shot.start,
        )
        if not shot_list:
            issues.append(f"segment {segment_index}: not covered by any shot")
            continue
        cursor = 0.0
        for shot in shot_list:
            if abs(shot.start - cursor) > 1e-6:
                issues.append(
                    f"segment {segment_index}: gap/overlap before {shot.id} "
                    f"(expected {cursor:.3f}, got {shot.start:.3f})"
                )
            cursor = shot.end
            span = (shot.end - shot.start) * duration
            if span < MIN_SHOT_SECONDS:
                issues.append(f"{shot.id}: {span:.1f}s is shorter than {MIN_SHOT_SECONDS:.0f}s")
            if span > MAX_SHOT_SECONDS:
                issues.append(f"{shot.id}: {span:.1f}s is longer than {MAX_SHOT_SECONDS:.0f}s")

            first = shot.beats[0].at
            if first > 0.35:
                issues.append(f"{shot.id}: first beat at {first:.2f} (> 0.35)")
            points = [beat.at for beat in shot.beats] + [1.0]
            for before, after in zip(points, points[1:]):
                gap = (after - before) * span
                if gap > MAX_GAP_SECONDS:
                    issues.append(
                        f"{shot.id}: {gap:.1f}s without a beat "
                        f"({before:.2f}->{after:.2f})"
                    )
            for move in shot.camera:
                if len(move.motive.strip()) < 8:
                    issues.append(f"{shot.id}: camera move at {move.at:.2f} needs a motive")
        if abs(cursor - 1.0) > 1e-6:
            issues.append(
                f"segment {segment_index}: shots end at {cursor:.3f}, not 1.0"
            )

    long_lived = sum(1 for shot in sheet.shots if shot.long_lived)
    ratio = long_lived / len(sheet.shots)
    if ratio < MIN_LONG_LIVED_RATIO:
        issues.append(
            f"continuity: {long_lived}/{len(sheet.shots)} shots declare long-lived objects "
            f"({ratio:.0%} < {MIN_LONG_LIVED_RATIO:.0%})"
        )
    return issues


def shot_seconds(sheet: BeatSheet, segments: list[tuple[float, float]]) -> list[float]:
    durations = _segment_durations(segments)
    return [
        (shot.end - shot.start) * durations[shot.segment - 1] for shot in sheet.shots
    ]


def load_sheet(path: Path) -> BeatSheet:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"beat sheet must be a mapping: {path}")
    return BeatSheet.model_validate(data)


def load_segments(meta_path: Path) -> list[tuple[float, float]]:
    """Read (start, duration) from the measured narration meta."""
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    result: list[tuple[float, float]] = []
    for segment in segments:
        if "start_s" in segment:
            result.append((float(segment["start_s"]), float(segment["duration_s"])))
        else:
            result.append((float(segment["start"]), float(segment["duration"])))
    return result
