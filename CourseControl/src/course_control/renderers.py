"""Renderer capability registry.

The registry answers one question before any render starts: can this renderer
produce the shot?  It does not unify engine internals; it only gates dispatch.
"""
from __future__ import annotations

from typing import Iterable

RENDERER_CAPABILITIES: dict[str, frozenset[str]] = {
    "code_video": frozenset({
        "2d_vector", "html_ui", "kinetic_type", "word_events", "hard_cut",
        "dissolve", "transform", "particles", "population", "state_change",
        "data_viz", "3d_scene", "camera_move", "deterministic",
    }),
    "manim": frozenset({
        "2d_vector", "kinetic_type", "transform", "particles", "population",
        "state_change", "data_viz", "camera_move", "deterministic",
    }),
    "motion_canvas": frozenset({
        "2d_vector", "kinetic_type", "transform", "particles", "population",
        "data_viz", "camera_move", "deterministic",
    }),
    "blender": frozenset({
        "2d_vector", "transform", "particles", "population", "3d_scene",
        "camera_move", "deterministic",
    }),
}

RENDERERS = frozenset(RENDERER_CAPABILITIES)


def capabilities_for(name: str) -> frozenset[str]:
    try:
        return RENDERER_CAPABILITIES[name]
    except KeyError as exc:
        raise KeyError(f"unknown renderer: {name}") from exc


def missing_capabilities(name: str, required: Iterable[str]) -> list[str]:
    available = capabilities_for(name)
    return sorted({item for item in required if item not in available})


def require_capabilities(name: str, required: Iterable[str]) -> None:
    missing = missing_capabilities(name, required)
    if missing:
        raise ValueError(
            f"renderer '{name}' cannot produce this shot; missing: "
            + ", ".join(missing)
        )
