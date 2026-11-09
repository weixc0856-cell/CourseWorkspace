"""Objective scorecard for "does this film move like 3Blue1Brown?".

The score is deliberately mechanical: it reads the beat sheet, the measured
narration, the build report and the media QC, and returns a 0-100 breakdown.
It is a gate for the *workflow*, not a substitute for watching the film.
"""

from __future__ import annotations

from .beats import BeatSheet, shot_seconds, validate_sheet

TARGETS = {
    "beats_per_10s": 2.5,
    "long_lived": 0.6,
    "shot_seconds": (8.0, 12.0),
    "freeze_per_minute": 9.0,
}

WEIGHTS = {
    "motion": 25.0,
    "continuity": 20.0,
    "pacing": 15.0,
    "camera": 10.0,
    "gates": 15.0,
    "freeze": 15.0,
}


def _pacing(seconds: float) -> float:
    low, high = TARGETS["shot_seconds"]
    if low <= seconds <= high:
        return 1.0
    distance = low - seconds if seconds < low else seconds - high
    return max(0.0, 1.0 - distance / 6.0)


def _freeze(intervals: int, minutes: float) -> float:
    rate = intervals / max(minutes, 0.1)
    target = TARGETS["freeze_per_minute"]
    if rate <= target:
        return 1.0
    return max(0.0, 1.0 - (rate - target) / 9.0)


def score(
    sheet: BeatSheet,
    segments: list[tuple[float, float]],
    *,
    media_qc: dict | None = None,
    build_verdict: str | None = None,
    palette_ok: bool = True,
) -> dict:
    seconds = shot_seconds(sheet, segments)
    total = sum(seconds)
    shots = len(sheet.shots)
    beats = sum(len(shot.beats) for shot in sheet.shots)
    beats_per_10s = beats / max(total, 0.1) * 10.0
    long_lived = sum(1 for shot in sheet.shots if shot.long_lived) / max(shots, 1)
    average_shot = total / max(shots, 1)
    moves = [(shot.id, move) for shot in sheet.shots for move in shot.camera]
    motivated = sum(1 for _, move in moves if len(move.motive.strip()) >= 8)
    issues = validate_sheet(sheet, segments, palette_ok=palette_ok)

    freeze_intervals = len((media_qc or {}).get("freeze_intervals", []))
    freeze_rate = freeze_intervals / max(total / 60.0, 0.1)

    components = {
        "motion": min(1.0, beats_per_10s / TARGETS["beats_per_10s"]) * WEIGHTS["motion"],
        "continuity": min(1.0, long_lived / TARGETS["long_lived"]) * WEIGHTS["continuity"],
        "pacing": _pacing(average_shot) * WEIGHTS["pacing"],
        "camera": (motivated / len(moves) if moves else 1.0) * WEIGHTS["camera"],
        "gates": (0.0 if issues or build_verdict == "fail" else WEIGHTS["gates"]),
        "freeze": _freeze(freeze_intervals, total / 60.0) * WEIGHTS["freeze"],
    }
    total_score = round(sum(components.values()), 1)
    return {
        "score": total_score,
        "components": {key: round(value, 1) for key, value in components.items()},
        "metrics": {
            "shots": shots,
            "total_seconds": round(total, 2),
            "average_shot_seconds": round(average_shot, 2),
            "beats": beats,
            "beats_per_10s": round(beats_per_10s, 2),
            "long_lived_ratio": round(long_lived, 2),
            "camera_moves": len(moves),
            "camera_motivated": motivated,
            "freeze_intervals": freeze_intervals,
            "freeze_per_minute": round(freeze_rate, 2),
            "build_verdict": build_verdict,
        },
        "issues": issues,
        "verdict": "pass" if not issues and build_verdict != "fail" else "fail",
    }
