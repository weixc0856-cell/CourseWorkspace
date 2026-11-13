"""Engine-neutral keyframe boards.

A board is the thing a person actually looks at before an engine renders: the
start, turn and end of one shot, blocked in the theme's own colours, with the
depth layers, the focal object and the motion written underneath.  It is an SVG
because the frames have to stay reviewable without a browser stack or a render.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from course_control.design.schema import Keyframe, KeyframeObject, Rect, ShotDesign

WIDTH = 1560
HEADER_H = 84
PANEL_W = 480
PANEL_H = 270
PANEL_GAP = 24
MARGIN = 32
NOTES_H = 150
HEIGHT = HEADER_H + PANEL_H + NOTES_H + 200

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(color: str, other: str, ratio: float) -> str:
    first, second = _rgb(color), _rgb(other)
    mixed = tuple(round(a + (b - a) * ratio) for a, b in zip(first, second))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def resolve_color(theme: dict, role: str) -> str:
    colors = theme.get("colors", {})
    if role in colors and isinstance(colors[role], str):
        return colors[role]
    semantics = theme.get("semantics", {})
    name = semantics.get(role) if isinstance(semantics, dict) else None
    if isinstance(name, str) and isinstance(colors.get(name), str):
        return colors[name]
    return colors.get("accent", "#E8733B")


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _frame_rect(rect: Rect, origin_x: float, origin_y: float) -> tuple[float, float, float, float]:
    """Normalised (bottom-left) rectangle to SVG (top-left) coordinates."""
    x = origin_x + rect.x * PANEL_W
    y = origin_y + (1 - (rect.y + rect.h)) * PANEL_H
    return x, y, rect.w * PANEL_W, rect.h * PANEL_H


def _panel(
    design: ShotDesign,
    frame: Keyframe,
    index: int,
    theme: dict,
    origin_y: float,
) -> list[str]:
    colors = theme.get("colors", {})
    paper = colors.get("paper", "#FBFAF7")
    surface = colors.get("surface", "#F3F1EA")
    border = colors.get("border", "#E3E0D7")
    ink = colors.get("ink", "#252A31")
    muted = colors.get("muted", "#6B7280")

    x0 = MARGIN + index * (PANEL_W + PANEL_GAP)
    parts = [
        f'<g id="panel-{frame.id}">',
        f'<rect x="{x0}" y="{origin_y}" width="{PANEL_W}" height="{PANEL_H}" rx="6" '
        f'fill="{paper}" stroke="{border}" stroke-width="1.5"/>',
    ]

    # Safe area, so an object leaving it is visible before render.
    sx, sy, sw, sh = _frame_rect(Rect(x=0.06, y=0.09, w=0.88, h=0.82), x0, origin_y)
    parts.append(
        f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{sw:.1f}" height="{sh:.1f}" fill="none" '
        f'stroke="{muted}" stroke-opacity="0.35" stroke-dasharray="5 6"/>'
    )

    # Depth is drawn as tone, not as labelled boxes: the subject layer is the
    # object itself, and labels for every layer would bury the frame.
    for layer in design.composition.depth_layers:
        if layer.role == "subject":
            continue
        lx, ly, lw, lh = _frame_rect(layer.rect, x0, origin_y)
        tint = _mix(paper, surface, 0.75 if layer.role == "background" else 0.55)
        parts.append(
            f'<rect x="{lx:.1f}" y="{ly:.1f}" width="{lw:.1f}" height="{lh:.1f}" rx="4" '
            f'fill="{tint}" fill-opacity="{0.5 if layer.role == "background" else 0.85}" '
            f'stroke="{border}" stroke-width="1" stroke-opacity="0.6"/>'
        )

    for obj in frame.objects:
        _draw_object(obj, design, theme, x0, origin_y, parts, ink, muted)

    if frame.id == "turn":
        for obj in frame.objects:
            if obj.id != design.composition.focal_object:
                continue
            cx, cy = design.composition.focal_point
            px = x0 + cx * PANEL_W
            py = origin_y + (1 - cy) * PANEL_H
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{resolve_color(theme, "accent")}"/>')

    parts.append(
        f'<text x="{x0 + 12}" y="{origin_y + PANEL_H + 22}" font-family="{FONT}" font-size="13" '
        f'font-weight="600" fill="{ink}">{frame.id.upper()} · {frame.at_s:g}s</text>'
    )
    parts.append(
        f'<text x="{x0 + 12}" y="{origin_y + PANEL_H + 42}" font-family="{FONT}" font-size="12" '
        f'fill="{muted}">{escape(frame.camera)}</text>'
    )
    parts.append("</g>")
    return parts


def _draw_object(
    obj: KeyframeObject,
    design: ShotDesign,
    theme: dict,
    origin_x: float,
    origin_y: float,
    parts: list[str],
    ink: str,
    muted: str,
) -> None:
    x, y, w, h = _frame_rect(obj.rect, origin_x, origin_y)
    color = resolve_color(theme, obj.color_role)
    focal = obj.id == design.composition.focal_object
    stroke_width = 2.6 if focal else 1.4
    fill_opacity = 0.22 if focal else 0.12
    parts.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" '
        f'fill="{color}" fill-opacity="{fill_opacity}" stroke="{color}" '
        f'stroke-width="{stroke_width}" stroke-opacity="{0.95 if focal else 0.7}"'
        f'{" stroke-dasharray=\"6 4\"" if obj.opacity < 1 else ""}/>'
    )
    label = obj.label if len(obj.label) <= 34 else obj.label[:33] + "…"
    lines = _wrap(label, max(int(w / 7.4), 8))
    lines = lines[:2] if h >= 30 else lines[:1]
    if lines:
        chip_w = min(max(len(line) for line in lines) * 6.9 + 12, w - 8)
        chip_h = 13 * len(lines) + 8
        parts.append(
            f'<rect x="{x + 4:.1f}" y="{y + 4:.1f}" width="{chip_w:.1f}" height="{chip_h:.1f}" '
            f'rx="3" fill="{theme.get("colors", {}).get("paper", "#FBFAF7")}" fill-opacity="0.88"/>'
        )
    baseline = y + 18 if h >= 30 else y + (h + 10) / 2
    for line_index, line in enumerate(lines):
        ty = baseline + line_index * 13
        if ty > y + h:
            break
        parts.append(
            f'<text x="{x + 10:.1f}" y="{ty:.1f}" font-family="{FONT}" font-size="12" '
            f'font-weight="{600 if focal else 400}" fill="{ink}">{escape(line)}</text>'
        )


def _beat_strip(design: ShotDesign, theme: dict, origin_y: float) -> list[str]:
    """A page is 100+ seconds: the three frames need a change schedule under them."""
    if not design.beats:
        return []
    colors = theme.get("colors", {})
    ink = colors.get("ink", "#252A31")
    muted = colors.get("muted", "#6B7280")
    border = colors.get("border", "#E3E0D7")
    accent = resolve_color(theme, "accent")

    x0 = MARGIN + 64
    x1 = WIDTH - MARGIN
    span = x1 - x0
    duration = max(design.duration_s, 1e-6)
    parts = [
        f'<text x="{MARGIN}" y="{origin_y + 4:.1f}" font-family="{FONT}" font-size="11" '
        f'fill="{muted}">beats</text>',
        f'<line x1="{x0}" y1="{origin_y}" x2="{x1}" y2="{origin_y}" stroke="{border}" stroke-width="1.5"/>',
    ]
    dense = span / max(len(design.beats), 1) < 72
    for index, beat in enumerate(design.beats):
        x = x0 + min(beat.at_s / duration, 1.0) * span
        parts.append(f'<circle cx="{x:.1f}" cy="{origin_y}" r="3.5" fill="{accent}"/>')
        if index % 2 and dense:
            continue
        label_y = origin_y - 8 if index % 2 == 0 else origin_y + 16
        parts.append(
            f'<text x="{x:.1f}" y="{label_y:.1f}" font-family="{FONT}" font-size="10.5" '
            f'text-anchor="middle" fill="{ink}">{beat.at_s:g}s {escape(beat.kind)}</text>'
        )
    return parts


def board_svg(design: ShotDesign, theme: dict) -> str:
    colors = theme.get("colors", {})
    paper = colors.get("paper", "#FBFAF7")
    ink = colors.get("ink", "#252A31")
    muted = colors.get("muted", "#6B7280")
    border = colors.get("border", "#E3E0D7")

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{paper}"/>',
        f'<text x="{MARGIN}" y="38" font-family="{FONT}" font-size="24" font-weight="700" '
        f'fill="{ink}">{escape(design.title)}</text>',
        f'<text x="{MARGIN}" y="62" font-family="{FONT}" font-size="13" fill="{muted}">'
        f'{design.shot_id} · {design.duration_s:g}s · {design.art_direction.family} · '
        f'{design.art_direction.theme} · {design.authorship}</text>',
    ]

    panel_y = HEADER_H
    for index, frame in enumerate(design.keyframes):
        parts.extend(_panel(design, frame, index, theme, panel_y))

    notes_y = HEADER_H + PANEL_H + 76
    for index, frame in enumerate(design.keyframes):
        x0 = MARGIN + index * (PANEL_W + PANEL_GAP)
        for line_index, line in enumerate(_wrap(frame.purpose, 62)[:3]):
            parts.append(
                f'<text x="{x0}" y="{notes_y + line_index * 17}" font-family="{FONT}" '
                f'font-size="12.5" fill="{ink}">{escape(line)}</text>'
            )
        for line_index, line in enumerate(_wrap(frame.change, 66)[:2]):
            parts.append(
                f'<text x="{x0}" y="{notes_y + 56 + line_index * 16}" font-family="{FONT}" '
                f'font-size="12" fill="{muted}">{escape(line)}</text>'
            )

    parts.extend(_beat_strip(design, theme, notes_y + 122))

    footer_y = HEIGHT - 74
    parts.append(
        f'<line x1="{MARGIN}" y1="{footer_y - 20}" x2="{WIDTH - MARGIN}" y2="{footer_y - 20}" '
        f'stroke="{border}" stroke-width="1"/>'
    )
    footer = [
        f"motion: {design.motion.primary}",
        f"secondary: {design.motion.secondary}",
        f"continuity: {design.continuity.spatial_rule}",
        f"hold: {design.motion.end_hold_s:g}s · negative space: {design.composition.negative_space} · "
        f"focus: {design.composition.focal_object}",
    ]
    for line_index, line in enumerate(footer):
        parts.append(
            f'<text x="{MARGIN}" y="{footer_y + line_index * 17}" font-family="{FONT}" '
            f'font-size="12" fill="{muted}">{escape(line)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"
