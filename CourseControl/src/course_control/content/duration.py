"""Course duration contract (R1-5B).

One course-level policy lives in ``lesson.yaml``. Page-level timing has exactly
one authority at a time:

* ``narration.timing = "planned"``  -> ``lecture_notes.md`` page budgets
* ``narration.timing = "measured"`` -> ``build/<slug>/narration/narration.meta.json``

The final video is checked against the resolved window. Nothing here stretches
or pads content to reach a target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from course_control.content.contracts import LessonConfig

PROFILES: dict[str, dict[str, float]] = {
    "standard": {"target": 1200.0, "min": 1080.0, "max": 1320.0},
    "short": {"target": 720.0, "min": 600.0, "max": 900.0},
    "news": {"target": 300.0, "min": 0.0, "max": 900.0},
}


@dataclass(frozen=True)
class ResolvedDuration:
    profile: str
    target: float
    minimum: float
    maximum: float
    page_tolerance: float
    declared_target: float | None = None
    declared_min: float | None = None
    declared_max: float | None = None

    @property
    def tolerance(self) -> float:
        return max(self.page_tolerance, 0.5)

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "target_seconds": self.target,
            "min_seconds": self.minimum,
            "max_seconds": self.maximum,
            "page_tolerance_seconds": self.page_tolerance,
        }


@dataclass(frozen=True)
class DurationProblem:
    level: Literal["error", "warning"]
    message: str


def resolve(lesson: LessonConfig) -> ResolvedDuration | None:
    """Return the resolved policy, or ``None`` when the lesson declares none."""
    policy = lesson.duration
    if policy is None:
        return None
    defaults = PROFILES[policy.profile]
    target = policy.target_seconds if policy.target_seconds is not None else defaults["target"]
    minimum = policy.min_seconds if policy.min_seconds is not None else defaults["min"]
    maximum = policy.max_seconds if policy.max_seconds is not None else defaults["max"]
    return ResolvedDuration(
        profile=policy.profile,
        target=float(target),
        minimum=float(minimum),
        maximum=float(maximum),
        page_tolerance=float(policy.page_tolerance_seconds),
        declared_target=policy.target_seconds,
        declared_min=policy.min_seconds,
        declared_max=policy.max_seconds,
    )


def window_problem(actual_s: float, policy: ResolvedDuration) -> DurationProblem | None:
    """Error when a final/summed duration leaves the allowed window."""
    if actual_s < policy.minimum - policy.tolerance:
        return DurationProblem(
            "error",
            f"duration {actual_s:.1f}s is below minimum {policy.minimum:.1f}s",
        )
    if actual_s > policy.maximum + policy.tolerance:
        return DurationProblem(
            "error",
            f"duration {actual_s:.1f}s exceeds maximum {policy.maximum:.1f}s",
        )
    return None


def planned_problems(planned_s: float, policy: ResolvedDuration) -> list[DurationProblem]:
    """Validate a planned (pre-production) total against the policy."""
    problems: list[DurationProblem] = []
    below = window_problem(planned_s, policy)
    if below is not None:
        problems.append(below)
    drift = abs(planned_s - policy.target)
    allowed_drift = max(policy.page_tolerance, policy.target * 0.02)
    if drift > allowed_drift:
        direction = "below" if planned_s < policy.target else "above"
        problems.append(
            DurationProblem(
                "warning",
                f"planned {planned_s:.1f}s is {drift:.1f}s {direction} target {policy.target:.1f}s",
            )
        )
    return problems


def duplicate_authority_problem(lesson: LessonConfig, policy: ResolvedDuration) -> DurationProblem | None:
    """``acceptance.notes_total_seconds`` is legacy; reject contradicting values."""
    legacy = lesson.acceptance.notes_total_seconds
    if legacy is None:
        return None
    if abs(legacy - policy.target) <= max(policy.page_tolerance, policy.target * 0.02):
        return None
    return DurationProblem(
        "error",
        "acceptance.notes_total_seconds="
        f"{legacy:.1f}s contradicts duration.target_seconds={policy.target:.1f}s",
    )


def frame_tolerance(policy: ResolvedDuration, fps: int) -> float:
    """One video frame in seconds, used for output comparisons."""
    return 1.0 / fps if fps > 0 else 0.0
