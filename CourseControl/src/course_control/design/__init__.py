"""Visual design layer: what a shot looks like before any engine draws it."""

from .planner import build_design
from .schema import VisualDesign

__all__ = ["VisualDesign", "build_design"]
