"""Per-stage timeouts with an explicit source.

A fixed 1800 s timeout is a guess; a 20-minute course needs more, a 60-second
sample needs less.  Timeouts scale from the lesson's duration policy and can be
overridden per stage in ``config/tools.yaml``:

    timeouts:
      compose: 7200
      render:blender: 3600

When a stage times out, ``run_command`` kills the whole process tree and
returns exit 124; the stage records the timeout and resume can re-run only that
stage.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from course_control.content.paths import LessonPaths

DEFAULT_SECONDS = {
    "capture_slides": 600,
    "render:motion_canvas": 1800,
    "render:manim": 1800,
    "render:blender": 1900,
    "render:code_video": 1800,
    "collect": 600,
    "compose": 1800,
    "burn_subtitles": 900,
    "brand": 1800,
    "verify": 600,
}

# Stages whose work is proportional to the final runtime.
SCALES_WITH_DURATION = {
    "compose": 3.0,
    "burn_subtitles": 1.5,
    "brand": 1.0,
    "render:code_video": 2.0,
}


def _overrides(workspace: Path) -> dict:
    path = workspace / "config" / "tools.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    value = data.get("timeouts") if isinstance(data, dict) else None
    return value if isinstance(value, dict) else {}


def resolve_timeout(paths: LessonPaths, stage: str) -> int:
    if stage not in DEFAULT_SECONDS:
        raise KeyError(f"unknown stage timeout: {stage}")
    workspace = getattr(paths, "workspace", None)
    toolkit = _overrides(workspace) if workspace is not None else {}
    if stage in toolkit:
        try:
            override = int(toolkit[stage])
        except (TypeError, ValueError):
            override = 0
        if override > 0:
            return override
    baseline = DEFAULT_SECONDS[stage]
    lesson = getattr(paths, "lesson", None)
    duration = getattr(lesson, "duration", None)
    target = getattr(duration, "target_seconds", None)
    scale = SCALES_WITH_DURATION.get(stage)
    if target and scale:
        baseline = max(baseline, int(math.ceil(float(target) * scale)))
    return baseline


__all__ = ["DEFAULT_SECONDS", "SCALES_WITH_DURATION", "resolve_timeout"]
