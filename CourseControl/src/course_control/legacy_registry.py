"""Registry of fields that still bridge the legacy timeline into V1.

``collect`` writes both ``shots.json`` and the normalized
``contracts/timeline.spec.json``.  The normalized view carries a handful of
``legacy_*`` fields because Remotion still needs the original shot semantics.
That bridge is allowed, but it must be enumerated: an unregistered ``legacy_*``
field is a second, silent contract.

Exit plan: each field is removed when its consumer stops reading it.  The
consumer is recorded here so the next migration can start from facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LegacyField:
    name: str
    consumer: str
    replacement: str
    removal: str
    reason: str


LEGACY_FIELDS: dict[str, LegacyField] = {
    "legacy_kind": LegacyField(
        "legacy_kind",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "ShotSpec.kind",
        "V1.1",
        "V1 shots have no kind discriminator yet; Remotion picks the layer by kind",
    ),
    "legacy_engine": LegacyField(
        "legacy_engine",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "ShotSpec.engine",
        "V1.1",
        "Engine is already normalized on the shot but the timeline keeps the raw value",
    ),
    "legacy_slide": LegacyField(
        "legacy_slide",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "ShotSpec.page",
        "V1.1",
        "Slide index is still needed to select captured frames",
    ),
    "legacy_presentation": LegacyField(
        "legacy_presentation",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "ShotSpec.presentation",
        "V1.1",
        "Overlay presentation modes are not part of the V1 shot schema",
    ),
    "legacy_transition": LegacyField(
        "legacy_transition",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "TimelineSpec.video[].transition",
        "V1.1",
        "Transition timing is normalized later; the raw block is still read",
    ),
    "legacy_motion": LegacyField(
        "legacy_motion",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "TimelineSpec.video[].motion",
        "V1.1",
        "Ken Burns parameters are not in the V1 shot schema",
    ),
    "legacy_generated_at": LegacyField(
        "legacy_generated_at",
        "CourseControl/src/course_control/v1_timeline.py",
        "TimelineSpec.created_at",
        "V1.1",
        "Provenance only; no renderer reads it",
    ),
    "legacy_total_duration_s": LegacyField(
        "legacy_total_duration_s",
        "CourseControl/src/course_control/v1_timeline.py",
        "TimelineSpec.total_frames",
        "V1.1",
        "Duration is derivable from total_frames and fps",
    ),
    "legacy_annotations": LegacyField(
        "legacy_annotations",
        "RemotionStudio/src/compositions/CourseTimeline.tsx",
        "TimelineSpec.overlays",
        "V1.1",
        "Annotation blocks have no V1 overlay equivalent yet",
    ),
}


def _walk(value: Any, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}" if path else str(key)
            if str(key).startswith("legacy_"):
                found.append((str(key), here))
            found.extend(_walk(item, here))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk(item, f"{path}[{index}]"))
    return found


def audit(payload: Any) -> dict:
    """Return registered and unregistered legacy field usage."""
    used = _walk(payload)
    names = sorted({name for name, _ in used})
    unknown = [name for name in names if name not in LEGACY_FIELDS]
    return {
        "fields": names,
        "unknown": unknown,
        "locations": sorted({location for _, location in used}),
        "registered": [name for name in names if name in LEGACY_FIELDS],
    }


def problems(payload: Any) -> list[str]:
    report = audit(payload)
    issues = [
        f"unregistered legacy field: {name} (add it to legacy_registry.py with an owner and removal)"
        for name in report["unknown"]
    ]
    return issues


__all__ = ["LEGACY_FIELDS", "LegacyField", "audit", "problems"]
