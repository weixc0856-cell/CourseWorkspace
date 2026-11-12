"""Design tokens, layout templates and layout checks.

Layout is a director responsibility: a shot picks a validated template with
normalised regions before the engine draws anything.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel

Role = Literal["title", "main_visual", "explanation", "caption", "footer", "subtitle"]


class DesignSystem(StrictModel):
    canvas_width: int = Field(default=1920, gt=0)
    canvas_height: int = Field(default=1080, gt=0)
    safe_margin_px: int = Field(default=96, ge=0)
    spacing_px: int = Field(default=8, gt=0)
    background: str = "#FBFAF7"
    surface: str = "#F3F1EA"
    ink: str = "#252A31"
    body: str = "#2E3338"
    muted: str = "#6B7280"
    accent: str = "#E8733B"
    navy: str = "#12324A"
    blue: str = "#4A82B8"
    teal: str = "#42A69A"
    purple: str = "#7A6FB0"
    red: str = "#C75B55"
    flow: str = "#A8C6DE"
    divider: str = "#E3E0D7"
    typography: dict[str, int] = Field(
        default_factory=lambda: {
            "display": 60,
            "heading_1": 52,
            "heading_2": 40,
            "body": 30,
            "label": 24,
            "caption": 20,
        }
    )

    @property
    def safe_x(self) -> float:
        return self.safe_margin_px / self.canvas_width

    @property
    def safe_y(self) -> float:
        return self.safe_margin_px / self.canvas_height


class Region(StrictModel):
    role: Role
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class TemplateConstraints(StrictModel):
    min_main_visual_area: float = Field(default=0.25, ge=0, le=1)
    min_title_height: float = Field(default=0.08, ge=0, le=1)
    subtitle_band: float = Field(default=0.08, ge=0, le=0.3)
    max_title_chars: int = Field(default=90, gt=0)
    max_body_chars: int = Field(default=420, gt=0)


class LayoutTemplate(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    typography: dict[str, str] = Field(default_factory=dict)
    regions: list[Region] = Field(min_length=1)
    constraints: TemplateConstraints = Field(default_factory=TemplateConstraints)

    @model_validator(mode="after")
    def _roles_unique(self):
        roles = [region.role for region in self.regions]
        if len(roles) != len(set(roles)):
            raise ValueError("region roles must be unique")
        return self

    def region(self, role: str) -> Region | None:
        return next((item for item in self.regions if item.role == role), None)


class LayoutCheck(StrictModel):
    id: str
    level: Literal["error", "warning", "info"]
    rule: str
    message: str
