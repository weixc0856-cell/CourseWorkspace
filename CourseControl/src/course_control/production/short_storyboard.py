"""The JSON contract that drives the component-based short.

Remotion reads this file directly; this module is the validator that keeps a
typo from reaching the renderer.  It checks structure and the props each
component actually needs, not taste.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel

SceneKind = Literal[
    "statement", "split_compare", "paper_highlight", "metric_bar", "simple_flow"
]
THEMES = ("editorial_science", "deep_space", "engineering_studio")


class ShortCaption(StrictModel):
    index: int | None = Field(default=None, ge=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    en: str = Field(min_length=1)
    zh: str | None = None
    # Spoken form when it differs from the display text (formulas, symbols).
    tts: str | None = None

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("caption end_s must be greater than start_s")
        return self


class ShortScene(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")
    kind: SceneKind
    duration_s: float = Field(gt=0)
    purpose: Literal['explain', 'demonstrate', 'compare', 'orient', 'summarize', 'emote']
    props: dict

    @model_validator(mode="after")
    def _required_props(self):
        props = self.props
        if self.kind == "statement" and not str(props.get("text") or "").strip():
            raise ValueError("statement needs props.text")
        if self.kind == "split_compare":
            for side in ("left", "right"):
                value = props.get(side)
                if not isinstance(value, dict) or not str(value.get("title") or "").strip():
                    raise ValueError(f"split_compare needs props.{side}.title")
        if self.kind == "paper_highlight":
            if not str(props.get("image") or "").strip():
                raise ValueError("paper_highlight needs props.image")
            box = props.get("box")
            if not isinstance(box, dict):
                raise ValueError("paper_highlight needs props.box")
            for key in ("x", "y", "w", "h"):
                if not isinstance(box.get(key), (int, float)):
                    raise ValueError(f"paper_highlight props.box.{key} must be a number")
            if not (0 <= box["x"] <= 1 and 0 <= box["y"] <= 1):
                raise ValueError("paper_highlight box origin must be inside 0-1")
            if not (0 < box["w"] <= 1 and 0 < box["h"] <= 1):
                raise ValueError("paper_highlight box size must be within 0-1")
            if box["x"] + box["w"] > 1.0001 or box["y"] + box["h"] > 1.0001:
                raise ValueError("paper_highlight box runs outside the image")
        if self.kind == "metric_bar":
            data = props.get("data")
            if not isinstance(data, list) or not data:
                raise ValueError("metric_bar needs a non-empty props.data")
            for item in data:
                if not isinstance(item, dict) or not str(item.get("label") or "").strip():
                    raise ValueError("metric_bar data items need a label")
                if not isinstance(item.get("value"), (int, float)):
                    raise ValueError("metric_bar data items need a numeric value")
        if self.kind == "simple_flow":
            steps = props.get("steps")
            if not isinstance(steps, list) or not steps:
                raise ValueError("simple_flow needs a non-empty props.steps")
            for item in steps:
                if not isinstance(item, dict) or not str(item.get("label") or "").strip():
                    raise ValueError("simple_flow steps need a label")
        return self


class ShortStoryboard(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    theme: Literal["editorial_science", "deep_space", "engineering_studio"] = "editorial_science"
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9"
    fps: int = Field(default=30, ge=1, le=120)
    audio: str | None = None
    scenes: list[ShortScene] = Field(min_length=1)
    captions: list[ShortCaption] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_scene_ids(self):
        ids = [scene.id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("short scene ids must be unique")
        previous = 0.0
        for caption in self.captions:
            if caption.start_s + 0.001 < previous:
                raise ValueError("captions must be ordered and non-overlapping")
            previous = caption.end_s
        return self

    @property
    def total_seconds(self) -> float:
        return round(sum(scene.duration_s for scene in self.scenes), 3)


class ShortStoryboardError(ValueError):
    pass


def load_short(path: Path) -> ShortStoryboard:
    path = Path(path)
    if not path.is_file():
        raise ShortStoryboardError(f"short storyboard not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ShortStoryboard.model_validate(data)
    except (OSError, ValueError) as exc:
        raise ShortStoryboardError(f"invalid short storyboard {path}: {exc}") from exc
