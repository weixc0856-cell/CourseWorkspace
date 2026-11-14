"""Preview and release rendering.

Preview changes cost, never design: same scenes, cameras, animation, fonts and
timing at a smaller raster.  The output is a review artifact, not a delivery.
"""

from course_control.preview.profile import (
    PREVIEW_SHORT_EDGE,
    PreviewLevel,
    PreviewProfile,
    RenderMode,
    preview_size,
    profile_for,
)
from course_control.preview.units import PreviewUnit, plan_lesson_units

__all__ = [
    "PREVIEW_SHORT_EDGE",
    "PreviewLevel",
    "PreviewProfile",
    "PreviewUnit",
    "RenderMode",
    "plan_lesson_units",
    "preview_size",
    "profile_for",
]
