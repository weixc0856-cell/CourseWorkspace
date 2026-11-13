"""The visual design layer: what a shot looks like before any engine draws.

The director decides what a shot is *for*.  This layer decides what the viewer
actually sees: art direction, blocking, three keyframes, motion and continuity.
It is engine-neutral on purpose — Manim, Blender, Motion Canvas and Remotion all
read the same design, and each keeps its own material and lighting.

A design is either ``authored`` (someone made these decisions) or ``derived``
(a deterministic draft from the shot and the outline).  The distinction travels
with the artifact so a draft is never mistaken for a decision.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import SceneTheme, StrictModel

Family = Literal["geometric", "engineering", "editorial", "cinematic"]
LayerRole = Literal["background", "midground", "subject", "foreground"]
FrameState = Literal["start", "turn", "end"]
Contrast = Literal["quiet", "balanced", "dramatic"]
Authorship = Literal["derived", "authored"]
Level = Literal["error", "warning", "info"]
NegativeSpace = Literal["left", "right", "top", "bottom"]


class Rect(StrictModel):
    """A normalised frame rectangle.  ``y`` is the bottom edge, like the layout library."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_frame(self):
        if self.x + self.w > 1 + 1e-6 or self.y + self.h > 1 + 1e-6:
            raise ValueError("rect must stay inside the frame")
        return self

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def area(self) -> float:
        return self.w * self.h


class ArtDirection(StrictModel):
    theme: SceneTheme
    family: Family
    atmosphere: str = Field(min_length=1)
    contrast: Contrast = "balanced"
    note: str = ""


class DepthLayer(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    role: LayerRole
    rect: Rect
    contrast: Contrast = "quiet"
    content: str = Field(min_length=1)


class Composition(StrictModel):
    focal_object: str = Field(min_length=1)
    focal_point: tuple[float, float] = (0.5, 0.5)
    negative_space: NegativeSpace = "right"
    hierarchy: list[str] = Field(min_length=1)
    depth_layers: list[DepthLayer] = Field(min_length=1)
    rule: str = ""

    @model_validator(mode="after")
    def _focus_in_hierarchy(self):
        if self.focal_object not in self.hierarchy:
            raise ValueError("focal_object must lead the hierarchy")
        if self.hierarchy[0] != self.focal_object:
            raise ValueError("focal_object must be first in the hierarchy")
        for axis in self.focal_point:
            if not 0.0 <= axis <= 1.0:
                raise ValueError("focal_point must be normalised")
        return self


class KeyframeObject(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    label: str = Field(min_length=1)
    rect: Rect
    color_role: str = Field(default="accent", min_length=1)
    emphasis: bool = False
    opacity: float = Field(default=1.0, gt=0, le=1)


class Keyframe(StrictModel):
    id: FrameState
    at_s: float = Field(ge=0)
    purpose: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    change: str = Field(min_length=1)
    objects: list[KeyframeObject] = Field(min_length=1)


class MotionPlan(StrictModel):
    primary: str = Field(min_length=1)
    secondary: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    end_hold_s: float = Field(default=1.5, ge=0, le=10)


BeatKind = Literal[
    "reveal", "transform", "highlight", "flow", "camera", "annotation", "compare", "connect"
]


class Beat(StrictModel):
    """One change inside a page.  Three keyframes cannot carry a 120 s page alone."""

    at_s: float = Field(ge=0)
    kind: BeatKind
    action: str = Field(min_length=4)
    object: str | None = None


class ContinuityPlan(StrictModel):
    persistent_objects: list[str] = Field(default_factory=list)
    carries_from: str | None = None
    spatial_rule: str = Field(min_length=1)


class ShotDesign(StrictModel):
    shot_id: str = Field(pattern=r"^shot_[0-9]{3}$")
    title: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    concept: str = Field(min_length=1)
    art_direction: ArtDirection
    composition: Composition
    motion: MotionPlan
    keyframes: list[Keyframe] = Field(min_length=3, max_length=3)
    beats: list[Beat] = Field(default_factory=list)
    continuity: ContinuityPlan
    on_screen_text: list[str] = Field(default_factory=list)
    authorship: Authorship = "derived"

    @model_validator(mode="after")
    def _three_keyframes_in_order(self):
        states = [frame.id for frame in self.keyframes]
        if states != ["start", "turn", "end"]:
            raise ValueError("keyframes must be start, turn, end in that order")
        times = [frame.at_s for frame in self.keyframes]
        if times != sorted(times) or len(set(times)) != 3:
            raise ValueError("keyframe times must increase")
        if times[-1] > self.duration_s + 1e-6:
            raise ValueError("last keyframe must fall inside the shot")
        beat_times = [beat.at_s for beat in self.beats]
        if len(set(beat_times)) != len(beat_times):
            raise ValueError("beats must not share a time")
        if beat_times != sorted(beat_times):
            raise ValueError("beats must be ordered by time")
        if beat_times and beat_times[-1] > self.duration_s + 1e-6:
            raise ValueError("last beat must fall inside the shot")
        return self

    def max_beat_gap_s(self) -> float:
        """The longest stretch inside the page with nothing scheduled."""
        marks = [0.0] + [beat.at_s for beat in self.beats] + [self.duration_s]
        return max(later - earlier for earlier, later in zip(marks, marks[1:]))

    def keyframe(self, state: FrameState) -> Keyframe:
        return next(frame for frame in self.keyframes if frame.id == state)


class DesignCheck(StrictModel):
    id: str
    level: Level
    rule: str
    message: str
    shot_id: str | None = None


class VisualDesign(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str
    theme_default: SceneTheme
    lesson_style_background: str
    shots: list[ShotDesign] = Field(min_length=1)
    checks: list[DesignCheck] = Field(default_factory=list)

    def shot(self, shot_id: str) -> ShotDesign:
        return next(item for item in self.shots if item.shot_id == shot_id)

    @property
    def errors(self) -> int:
        return sum(1 for item in self.checks if item.level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.checks if item.level == "warning")
