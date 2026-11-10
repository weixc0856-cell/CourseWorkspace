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


def _profile_score(
    sheet: BeatSheet,
    segments: list[tuple[float, float]],
    *,
    registry,
    media_qc: dict | None,
    build_verdict: str | None,
    palette_ok: bool,
) -> dict:
    from .beats import shot_seconds

    seconds = shot_seconds(sheet, segments)
    total = sum(seconds)
    shots = len(sheet.shots)
    beats = sum(len(shot.beats) for shot in sheet.shots)
    beats_per_10s = beats / max(total, 0.1) * 10.0
    cut_rate = shots / max(total, 0.1) * 10.0
    issues = validate_sheet(sheet, segments, palette_ok=palette_ok, registry=registry)

    specs = {}
    for shot in sheet.shots:
        name = shot.grammar or sheet.grammar
        specs[shot.id] = (name, registry.get(name))

    # pacing: each shot judged against its own window, weighted by duration.
    pacing = 0.0
    for shot, span in zip(sheet.shots, seconds):
        _, spec = specs[shot.id]
        low, high = spec.shot_seconds.min, spec.shot_seconds.max
        if low <= span <= high:
            factor = 1.0
        else:
            distance = low - span if span < low else span - high
            factor = max(0.0, 1.0 - distance / 6.0)
        pacing += factor * span
    pacing = pacing / max(total, 0.1)

    # continuity only counts shots whose grammar asks for it.
    required = [shot for shot in sheet.shots if specs[shot.id][1].constraints.long_lived_ratio_min > 0]
    if required:
        needed = max(specs[shot.id][1].constraints.long_lived_ratio_min for shot in required)
        declared = sum(1 for shot in required if shot.long_lived)
        continuity = min(1.0, (declared / len(required)) / needed)
    else:
        continuity = 1.0

    # Motion is judged per shot against its own grammar, weighted by duration.
    # A global maximum would let a 6-action/10s kinetic shot punish a 1-action/10s
    # simulation shot in the same film.
    motion = 0.0
    for shot, span in zip(sheet.shots, seconds):
        spec = specs[shot.id][1]
        density = len(shot.beats) / max(span, 0.1) * 10.0
        motion += min(1.0, density / spec.constraints.min_actions_per_10s) * span
    motion = motion / max(total, 0.1)
    moves = [(shot.id, move) for shot in sheet.shots for move in shot.camera]
    if not moves:
        camera = 1.0
    else:
        needs_motive = any(spec.constraints.camera_motive_required for _, spec in specs.values())
        if not needs_motive:
            camera = 1.0
        else:
            motivated = sum(1 for _, move in moves if len(move.motive.strip()) >= 8)
            camera = motivated / len(moves)

    freeze_intervals = len((media_qc or {}).get("freeze_intervals", []))
    freeze_rate = freeze_intervals / max(total / 60.0, 0.1)
    freeze_counts = any(spec.constraints.freeze_counts_against for _, spec in specs.values())
    freeze = _freeze(freeze_intervals, total / 60.0) if freeze_counts else 1.0

    components = {
        "motion": motion * WEIGHTS["motion"],
        "continuity": continuity * WEIGHTS["continuity"],
        "pacing": pacing * WEIGHTS["pacing"],
        "camera": camera * WEIGHTS["camera"],
        "gates": (0.0 if issues or build_verdict == "fail" else WEIGHTS["gates"]),
        "freeze": freeze * WEIGHTS["freeze"],
    }
    return {
        "score": round(sum(components.values()), 1),
        "components": {key: round(value, 1) for key, value in components.items()},
        "metrics": {
            "shots": shots,
            "total_seconds": round(total, 2),
            "average_shot_seconds": round(total / max(shots, 1), 2),
            "beats": beats,
            "beats_per_10s": round(beats_per_10s, 2),
            "cut_rate_per_10s": round(cut_rate, 2),
            "long_lived_ratio": round(
                sum(1 for shot in required if shot.long_lived) / max(len(required), 1), 2
            ),
            "camera_moves": len(moves),
            "freeze_intervals": freeze_intervals,
            "freeze_per_minute": round(freeze_rate, 2),
            "build_verdict": build_verdict,
        },
        "grammars": {shot.id: specs[shot.id][0] for shot in sheet.shots},
        "issues": issues,
        "verdict": "pass" if not issues and build_verdict != "fail" else "fail",
        "release_gate": "metric_only",
    }


def score(
    sheet: BeatSheet,
    segments: list[tuple[float, float]],
    *,
    media_qc: dict | None = None,
    build_verdict: str | None = None,
    palette_ok: bool = True,
    registry=None,
    profile: str | None = None,
) -> dict:
    if profile:
        sheet = sheet.model_copy(update={"grammar": profile})
    if registry is not None:
        return _profile_score(
            sheet,
            segments,
            registry=registry,
            media_qc=media_qc,
            build_verdict=build_verdict,
            palette_ok=palette_ok,
        )
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
