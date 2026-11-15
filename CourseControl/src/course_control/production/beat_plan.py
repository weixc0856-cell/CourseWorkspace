"""Validate a beat plan: a beat is a sequence of component instances.

The composition only assembles; pacing is decided here. Every instance declares
its component, props and duration, and the durations must add up to the beat.
A mismatch fails instead of silently stretching one component.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

TOLERANCE = 0.01


class BeatPlanError(ValueError):
    pass


@dataclass
class Instance:
    component: str
    duration: float
    props: dict


@dataclass
class Beat:
    id: str
    seconds: float
    instances: list[Instance]


def load_plan(path: Path) -> list[Beat]:
    if not path.is_file():
        raise BeatPlanError(f"beat plan not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BeatPlanError(f"invalid YAML in {path}: {exc}") from exc
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise BeatPlanError(f"{path}: beats must be a non-empty list")
    result = []
    for entry in beats:
        beat_id = str(entry.get("id") or "")
        if not beat_id:
            raise BeatPlanError("a beat has no id")
        seconds = float(entry.get("seconds") or 0)
        if seconds <= 0:
            raise BeatPlanError(f"beat {beat_id}: seconds must be positive")
        instances = []
        for item in entry.get("instances") or []:
            component = str(item.get("component") or "")
            duration = float(item.get("duration") or 0)
            if not component:
                raise BeatPlanError(f"beat {beat_id}: an instance has no component")
            if duration <= 0:
                raise BeatPlanError(f"beat {beat_id}: instance {component} has no duration")
            instances.append(Instance(component=component, duration=duration, props=item.get("props") or {}))
        if not instances:
            raise BeatPlanError(f"beat {beat_id}: no instances")
        total = round(sum(item.duration for item in instances), 3)
        if abs(total - seconds) > TOLERANCE:
            raise BeatPlanError(
                f"beat {beat_id}: instances sum to {total}s but the beat is {seconds}s"
            )
        result.append(Beat(id=beat_id, seconds=seconds, instances=instances))
    return result
