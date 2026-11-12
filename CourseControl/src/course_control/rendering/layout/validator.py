"""Static layout checks: safe area, overlap, hierarchy, visual weight, capacity."""
from __future__ import annotations

from course_control.rendering.layout.library import DESIGN
from course_control.rendering.layout.schema import DesignSystem, LayoutCheck, LayoutTemplate


def _overlap(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    width = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    height = max(0.0, min(ay1, by1) - max(ay0, by0))
    return width * height


def _capacity(region, font_px: int, design: DesignSystem) -> int:
    chars_per_line = max(1, int(region.w * design.canvas_width / (font_px * 0.55)))
    lines = max(1, int(region.h * design.canvas_height / (font_px * 1.3)))
    return chars_per_line * lines


def validate_template(template: LayoutTemplate, design: DesignSystem = DESIGN) -> list[LayoutCheck]:
    checks: list[LayoutCheck] = []
    safe_x, safe_y = design.safe_x, design.safe_y
    for region in template.regions:
        if region.x < safe_x - 1e-6 or region.y < safe_y - 1e-6:
            checks.append(
                LayoutCheck(
                    id="layout.safe_margin",
                    level="error",
                    rule="region starts inside the safe margin",
                    message=f"{region.role} starts at ({region.x:.3f}, {region.y:.3f})",
                )
            )
        if region.x + region.w > 1 - safe_x + 1e-6 or region.y + region.h > 1 - safe_y + 1e-6:
            checks.append(
                LayoutCheck(
                    id="layout.safe_margin",
                    level="error",
                    rule="region ends inside the safe margin",
                    message=f"{region.role} ends at ({region.x + region.w:.3f}, {region.y + region.h:.3f})",
                )
            )

    for index, first in enumerate(template.regions):
        for second in template.regions[index + 1 :]:
            area = _overlap(first.box, second.box)
            if area > 0.0005:
                checks.append(
                    LayoutCheck(
                        id="layout.overlap",
                        level="error",
                        rule="regions do not overlap",
                        message=f"{first.role} overlaps {second.role} by {area:.4f}",
                    )
                )

    visual = template.region("main_visual")
    if visual is None:
        checks.append(
            LayoutCheck(
                id="layout.no_visual",
                level="error",
                rule="every template has a main visual region",
                message="main_visual missing",
            )
        )
    elif visual.area < template.constraints.min_main_visual_area:
        checks.append(
            LayoutCheck(
                id="layout.visual_area",
                level="error",
                rule=f"main visual at least {template.constraints.min_main_visual_area:.0%} of the canvas",
                message=f"{visual.area:.1%}",
            )
        )

    title = template.region("title")
    if title is None:
        checks.append(
            LayoutCheck(id="layout.no_title", level="error", rule="template has a title region", message="missing")
        )
    elif title.h < template.constraints.min_title_height:
        checks.append(
            LayoutCheck(
                id="layout.title_height",
                level="error",
                rule=f"title band at least {template.constraints.min_title_height:.0%} high",
                message=f"{title.h:.1%}",
            )
        )

    band = template.constraints.subtitle_band
    for region in template.regions:
        if region.role not in {"subtitle"} and region.y < band - 1e-6:
            checks.append(
                LayoutCheck(
                    id="layout.subtitle_band",
                    level="error",
                    rule="content stays above the subtitle band",
                    message=f"{region.role} starts at {region.y:.3f}, band is {band:.3f}",
                )
            )

    order = ["display", "heading_1", "heading_2", "body", "label", "caption"]
    sizes = [design.typography.get(name) for name in order]
    if any(size is None for size in sizes) or sizes != sorted(sizes, reverse=True):
        checks.append(
            LayoutCheck(
                id="layout.typography_order",
                level="error",
                rule="typography scale is strictly descending",
                message=str(design.typography),
            )
        )
    return checks


def validate_content(
    template: LayoutTemplate,
    title_chars: int,
    body_chars: int = 0,
    bullet_count: int = 0,
    design: DesignSystem = DESIGN,
) -> list[LayoutCheck]:
    checks: list[LayoutCheck] = []
    title = template.region("title")
    if title is not None:
        capacity = _capacity(title, design.typography["heading_1"], design)
        if title_chars > min(capacity, template.constraints.max_title_chars):
            checks.append(
                LayoutCheck(
                    id="layout.title_capacity",
                    level="error",
                    rule="title fits its region",
                    message=f"{title_chars} chars > {min(capacity, template.constraints.max_title_chars)}",
                )
            )
    explanation = template.region("explanation")
    if explanation is not None and body_chars:
        capacity = _capacity(explanation, design.typography["body"], design)
        if body_chars > min(capacity, template.constraints.max_body_chars):
            checks.append(
                LayoutCheck(
                    id="layout.body_capacity",
                    level="error",
                    rule="body fits the explanation region",
                    message=f"{body_chars} chars > {min(capacity, template.constraints.max_body_chars)}",
                )
            )
    if bullet_count > 4:
        checks.append(
            LayoutCheck(
                id="layout.bullets",
                level="warning",
                rule="keep bullets at or below four",
                message=f"{bullet_count} bullets",
            )
        )
    return checks


def ok(checks: list[LayoutCheck]) -> bool:
    return not any(check.level == "error" for check in checks)
