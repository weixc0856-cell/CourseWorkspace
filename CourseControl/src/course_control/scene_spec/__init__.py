"""Scene specification contracts for the asset-based 3D pipeline.

An *environment* owns the reusable set (terrain, sky, set dressing, lights).
A *shot* owns the camera, timing and render settings and references one
environment.  This is the Level 2 / Level 3 split from the production review;
the asset library is Level 1.
"""
from .models import EnvironmentSpec, ShotSpec, load_spec
from .validate import validate_spec

__all__ = ["EnvironmentSpec", "ShotSpec", "load_spec", "validate_spec"]
