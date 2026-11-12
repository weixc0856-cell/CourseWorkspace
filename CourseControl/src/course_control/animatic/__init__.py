"""Animatic: a low-resolution, narration-locked preview of the real timeline.

``course-control animatic --lesson <slug>`` turns the units of a lesson's
timeline into short 480p segments, plays them back to back and muxes the
narration over them.  It is a decision tool: watch it before committing render
time, and re-run it after changing one shot.
"""

from .builder import build
from .report import write_artifacts
from .timeline import DEFAULT_SIZE, FPS, AnimaticError, Timeline, resolve, resolve_build

__all__ = [
    "AnimaticError",
    "DEFAULT_SIZE",
    "FPS",
    "Timeline",
    "build",
    "resolve",
    "resolve_build",
    "write_artifacts",
]
