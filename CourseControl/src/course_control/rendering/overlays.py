"""Scene overlays rendered by Remotion instead of baked into a captured plate.

A lesson can declare ``compose.overlay: <kind>``.  ``collect`` then embeds the
overlay payload in the V1 timeline metadata, and ``CourseTimeline`` draws it on
top of the base video.  Keeping the overlay out of the captured plate means the
world render stays a pure function of the simulation while the chart, labels and
typography can change without re-rendering 4,000 frames.
"""
from __future__ import annotations

import json

HAZARD_BIN_YEARS = 5


def _hazard_bins(hazard: list) -> list[float]:
    bins: list[float] = []
    for start in range(0, len(hazard), HAZARD_BIN_YEARS):
        window = [value for value in hazard[start : start + HAZARD_BIN_YEARS] if value is not None]
        bins.append(round(sum(window) / len(window), 4) if window else 0.0)
    return bins


def aging_hud(paths) -> dict | None:
    """Per-frame HUD samples for the aging plate, ready for the React overlay."""
    shot = next((item for item in paths.storyboard.shots if item.engine == "code_video"), None)
    if shot is None:
        return None
    scene_path, _ = paths.scene_path(shot)
    project = scene_path.parent
    aging_path = project / "aging.json"
    timing_path = project / "timing.json"
    if not aging_path.is_file() or not timing_path.is_file():
        return None
    aging = json.loads(aging_path.read_text(encoding="utf-8"))
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    total = float(timing.get("total") or 0)
    split = next(
        (float(segment["start"]) for segment in timing.get("segments", []) if segment.get("id") == "s08"),
        total * 0.52,
    )

    segments = []
    for index, scenario in enumerate(aging.get("scenarios", [])):
        population: list[int] = []
        mean_age: list[float | None] = []
        mutation: list[float] = []
        hazard: list[list[float]] = []
        for frame in scenario.get("frames", []):
            alive = [agent for agent in frame.get("agents", []) if agent[4]]
            population.append(int(frame.get("population") or 0))
            mean_age.append(None if frame.get("mean_death_age") is None else round(float(frame["mean_death_age"]), 1))
            mutation.append(round(sum(agent[5] for agent in alive) / len(alive), 2) if alive else 0.0)
            hazard.append(_hazard_bins(frame.get("hazard") or []))
        segments.append(
            {
                "id": scenario.get("id"),
                "label": scenario.get("label"),
                "start": round(0.0 if index == 0 else split, 3),
                "end": round(split if index == 0 else total, 3),
                "population": population,
                "mean_age": mean_age,
                "mutation": mutation,
                "hazard": hazard,
            }
        )
    return {
        "kind": "aging_hud",
        "title": "WHY AGING EVOLVES",
        "split": round(split, 3),
        "total": round(total, 3),
        "fps": int(aging.get("fps") or 30),
        "segments": segments,
    }


OVERLAYS = {"aging_hud": aging_hud}


def build_overlay(paths) -> dict | None:
    """Return the payload for the lesson's declared overlay, if any."""
    compose = getattr(getattr(paths, "lesson", None), "compose", None)
    kind = getattr(compose, "overlay", None)
    builder = OVERLAYS.get(kind or "")
    if builder is None:
        return None
    return builder(paths)


__all__ = ["OVERLAYS", "build_overlay", "aging_hud"]
