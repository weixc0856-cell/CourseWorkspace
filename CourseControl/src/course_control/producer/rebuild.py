"""Incremental rebuild: compare current shot fingerprints with the last run."""
from __future__ import annotations

from dataclasses import dataclass, field

from .schema import ShotFingerprint


@dataclass
class ShotDelta:
    shot_id: str
    change: str
    reasons: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


def diff_fingerprints(previous: list[ShotFingerprint], current: list[ShotFingerprint]) -> list[ShotDelta]:
    old = {item.shot_id: item for item in previous}
    new = {item.shot_id: item for item in current}
    deltas: list[ShotDelta] = []
    for shot_id in sorted(new, key=lambda value: (new[value].slide, value)):
        item = new[shot_id]
        before = old.get(shot_id)
        if before is None:
            deltas.append(
                ShotDelta(shot_id, "redesign", ["new shot"], ["write direction", "render scene", "compose"])
            )
            continue
        if item.content_sha256 != before.content_sha256:
            deltas.append(
                ShotDelta(
                    shot_id,
                    "redesign",
                    ["claim, visual, engine or page budget changed"],
                    ["rewrite direction", "render scene", "re-narrate if text changed", "compose"],
                )
            )
        elif item.scene_sha256 != before.scene_sha256:
            deltas.append(ShotDelta(shot_id, "re-render", ["scene source changed"], ["render scene", "compose"]))
        elif item.narration_sha256 != before.narration_sha256:
            deltas.append(
                ShotDelta(shot_id, "re-narrate", ["narration text changed"], ["regenerate narration", "recompose"])
            )
        elif item.direction_sha256 != before.direction_sha256:
            deltas.append(ShotDelta(shot_id, "recompose", ["direction file changed"], ["recompose"]))
    for shot_id in sorted(set(old) - set(new)):
        deltas.append(ShotDelta(shot_id, "redesign", ["shot removed"], ["recompose"]))
    return deltas
