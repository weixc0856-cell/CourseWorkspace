"""Backwards-compatible import location for the renderer capability registry."""
from ..renderers import (  # noqa: F401
    RENDERERS,
    RENDERER_CAPABILITIES,
    capabilities_for,
    missing_capabilities,
    require_capabilities,
)
