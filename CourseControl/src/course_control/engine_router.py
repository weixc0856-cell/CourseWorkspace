"""Content-driven animation engine routing (R1-3).

The router does not decide the course; it maps a shot's visual requirement to
the engine that is best at it. Authors can override the suggestion in
``storyboard.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass

MANIM_KINDS = {
    "math",
    "matrix",
    "formula",
    "algorithm",
    "diagram",
    "diagram2d",
    "flow",
    "structure2d",
    "attention",
}
BLENDER_KINDS = {
    "3d",
    "structure3d",
    "mechanical",
    "engineering",
    "fluid",
    "spatial",
    "product",
}
CODE_VIDEO_KINDS = {
    "motion_graphics",
    "kinetic_type",
    "svg",
    "canvas",
    "canvas2d",
    "threejs",
    "webgl",
    "shader",
    "infographic",
    "simulation",
}
REMOTION_KINDS = {
    "layout",
    "title",
    "chart",
    "text",
    "transition",
    "recording",
    "slide",
    "recap",
}

ENGINE_PROFILES = {
    "manim": "math_explainer",
    "blender": "engineering_3d",
    "remotion": "composition",
    "motion_canvas": "legacy",
    "code_video": "code_video",
}


@dataclass(frozen=True)
class VisualRequirement:
    kind: str
    needs_3d: bool = False
    has_existing_motion_asset: bool = False
    duration_s: float | None = None


@dataclass(frozen=True)
class EngineRoute:
    engine: str
    profile: str
    reason: str


def route_engine(requirement: VisualRequirement) -> EngineRoute:
    """Route a visual requirement to Manim, Blender, Remotion or Motion Canvas."""
    kind = requirement.kind.strip().lower()
    if requirement.has_existing_motion_asset:
        return EngineRoute(
            "motion_canvas",
            ENGINE_PROFILES["motion_canvas"],
            "existing Motion Canvas asset is kept as-is",
        )
    if requirement.needs_3d or kind in BLENDER_KINDS:
        return EngineRoute(
            "blender",
            ENGINE_PROFILES["blender"],
            "three-dimensional or engineering visual",
        )
    if kind in CODE_VIDEO_KINDS:
        return EngineRoute(
            "code_video",
            ENGINE_PROFILES["code_video"],
            "motion graphics / SVG / Canvas / Three.js shot",
        )
    if kind in MANIM_KINDS:
        return EngineRoute(
            "manim",
            ENGINE_PROFILES["manim"],
            "mathematical / algorithmic / two-dimensional structure",
        )
    if kind in REMOTION_KINDS:
        return EngineRoute(
            "remotion",
            ENGINE_PROFILES["remotion"],
            "layout, chart, title or composition layer",
        )
    return EngineRoute(
        "manim",
        ENGINE_PROFILES["manim"],
        "default for explanatory animation without a specific layout requirement",
    )
