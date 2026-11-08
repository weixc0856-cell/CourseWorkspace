"""The first layout library: eight validated page templates."""
from __future__ import annotations

from .schema import DesignSystem, LayoutTemplate, Region, TemplateConstraints

DESIGN = DesignSystem()

TITLE = Region(role="title", x=0.06, y=0.80, w=0.88, h=0.10)
CAPTION = Region(role="caption", x=0.06, y=0.09, w=0.88, h=0.05)
FOOTER = Region(role="footer", x=0.06, y=0.09, w=0.45, h=0.05)


def _template(
    template_id: str,
    name: str,
    content_type: str,
    regions: list[Region],
    min_visual: float,
    max_title: int = 90,
    max_body: int = 420,
) -> LayoutTemplate:
    return LayoutTemplate(
        id=template_id,
        name=name,
        content_type=content_type,
        typography={"title": "heading_1", "body": "body", "caption": "caption"},
        regions=[TITLE, *regions],
        constraints=TemplateConstraints(
            min_main_visual_area=min_visual,
            max_title_chars=max_title,
            max_body_chars=max_body,
        ),
    )


TEMPLATES: dict[str, LayoutTemplate] = {
    template.id: template
    for template in [
        _template(
            "title_intro",
            "Title intro",
            "title",
            [
                Region(role="main_visual", x=0.60, y=0.18, w=0.34, h=0.60),
                Region(role="explanation", x=0.06, y=0.55, w=0.48, h=0.20),
                CAPTION,
            ],
            min_visual=0.18,
            max_title=60,
            max_body=180,
        ),
        _template(
            "two_column",
            "Two-column comparison",
            "comparison",
            [
                Region(role="main_visual", x=0.06, y=0.18, w=0.40, h=0.58),
                Region(role="explanation", x=0.52, y=0.18, w=0.42, h=0.58),
                CAPTION,
            ],
            min_visual=0.20,
        ),
        _template(
            "process_flow",
            "Process flow",
            "process",
            [
                Region(role="main_visual", x=0.06, y=0.20, w=0.88, h=0.54),
                Region(role="caption", x=0.06, y=0.09, w=0.88, h=0.07),
            ],
            min_visual=0.42,
            max_body=120,
        ),
        _template(
            "principle_diagram",
            "Principle diagram",
            "principle",
            [
                Region(role="main_visual", x=0.06, y=0.18, w=0.58, h=0.58),
                Region(role="explanation", x=0.68, y=0.28, w=0.26, h=0.40),
                CAPTION,
            ],
            min_visual=0.30,
            max_body=260,
        ),
        _template(
            "formula_derivation",
            "Formula derivation",
            "formula",
            [
                Region(role="main_visual", x=0.06, y=0.28, w=0.58, h=0.46),
                Region(role="explanation", x=0.68, y=0.18, w=0.26, h=0.56),
                CAPTION,
            ],
            min_visual=0.24,
            max_body=320,
        ),
        _template(
            "data_chart",
            "Data chart",
            "chart",
            [
                Region(role="main_visual", x=0.06, y=0.18, w=0.58, h=0.58),
                Region(role="explanation", x=0.68, y=0.22, w=0.26, h=0.46),
                CAPTION,
            ],
            min_visual=0.30,
        ),
        _template(
            "code_demo",
            "Code demo",
            "code",
            [
                Region(role="main_visual", x=0.06, y=0.18, w=0.58, h=0.58),
                Region(role="explanation", x=0.68, y=0.18, w=0.26, h=0.52),
                CAPTION,
            ],
            min_visual=0.30,
        ),
        _template(
            "summary",
            "Summary",
            "summary",
            [
                Region(role="main_visual", x=0.06, y=0.18, w=0.48, h=0.58),
                Region(role="explanation", x=0.60, y=0.18, w=0.34, h=0.58),
                CAPTION,
            ],
            min_visual=0.25,
        ),
    ]
}


def get_template(template_id: str) -> LayoutTemplate:
    try:
        return TEMPLATES[template_id]
    except KeyError as exc:
        raise KeyError(f"unknown layout template: {template_id}") from exc


def choose_template(content_type: str, animation: str | None = None) -> str:
    """Map a page's visual kind (and optional scene stem) to a template."""
    if animation in {"cross_attention_flow", "loss_backprop", "residual_bypass"}:
        return "process_flow"
    mapping = {
        "title": "title_intro",
        "comparison": "two_column",
        "process": "process_flow",
        "diagram": "principle_diagram",
        "matrix": "principle_diagram",
        "formula": "formula_derivation",
        "chart": "data_chart",
        "code": "code_demo",
        "layout": "summary",
        "recap": "summary",
        "structure3d": "principle_diagram",
        "simulation": "process_flow",
    }
    return mapping.get(content_type, "principle_diagram")
