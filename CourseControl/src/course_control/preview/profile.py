"""Render modes, preview levels and the one place resolution is scaled."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PREVIEW_SHORT_EDGE = 480


class RenderMode(str, Enum):
    PREVIEW = "preview"
    RELEASE = "release"


class PreviewLevel(str, Enum):
    SHOT = "shot"
    SEGMENT = "segment"
    PROJECT = "project"


@dataclass(frozen=True)
class PreviewProfile:
    """What changes between a preview and a release render.

    ``scale`` is what a compositor wants (Remotion ``--scale``).  ``width`` and
    ``height`` are the exact output raster for engines that take a size.
    """

    mode: RenderMode
    level: PreviewLevel
    width: int
    height: int
    fps: int
    scale: float
    # Remotion's --scale must produce integer dimensions.  Render at a clean
    # half/quarter scale, then downscale to the exact preview raster with
    # ffmpeg.  This keeps the composition's layout untouched.
    render_scale: float = 1.0
    audio: bool = True

    @property
    def is_preview(self) -> bool:
        return self.mode is RenderMode.PREVIEW

    @property
    def label(self) -> str:
        return self.mode.value

    def as_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "level": self.level.value,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "scale": self.scale,
            "render_scale": self.render_scale,
            "audio": self.audio,
        }


def preview_size(width: int, height: int, short_edge: int = PREVIEW_SHORT_EDGE) -> tuple[int, int, float]:
    """Return (width, height, scale) with the short edge at ``short_edge``.

    Dimensions are rounded to even numbers so every encoder accepts them.
    """
    if width <= 0 or height <= 0:
        raise ValueError("source dimensions must be positive")
    scale = short_edge / min(width, height)
    target_w = max(2, int(round(width * scale / 2.0) * 2))
    target_h = max(2, int(round(height * scale / 2.0) * 2))
    return target_w, target_h, scale


def profile_for(
    mode: RenderMode | str,
    level: PreviewLevel | str,
    *,
    width: int,
    height: int,
    fps: int,
    audio: bool = True,
) -> PreviewProfile:
    mode = RenderMode(mode)
    level = PreviewLevel(level)
    if mode is RenderMode.RELEASE:
        return PreviewProfile(
            mode=mode,
            level=level,
            width=width,
            height=height,
            fps=fps,
            scale=1.0,
            render_scale=1.0,
            audio=audio,
        )
    target_w, target_h, scale = preview_size(width, height)
    render_scale = 1.0 if min(width, height) <= 540 else 0.5
    return PreviewProfile(
        mode=mode,
        level=level,
        width=target_w,
        height=target_h,
        fps=fps,
        scale=scale,
        render_scale=render_scale,
        audio=audio,
    )


__all__ = [
    "PREVIEW_SHORT_EDGE",
    "PreviewLevel",
    "PreviewProfile",
    "RenderMode",
    "preview_size",
    "profile_for",
]
