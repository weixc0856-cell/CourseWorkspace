"""Chinese-painting palettes adapted to the course design tokens.

Seven four-colour palettes extracted from classical Chinese painting, plus the
current light-editorial default.  A palette is a *family*, not a ready-to-use
UI theme: the roles below are derived deterministically so every palette meets
the same accessibility gates:

* ``ink`` on ``paper`` >= 7:1 (WCAG AAA for body text)
* ``focus`` / ``support`` on ``paper`` >= 3:1 (WCAG 1.4.11, graphical objects)
* ``muted`` on ``paper`` >= 4.5:1 (WCAG AA for secondary text)

When a palette has no dark enough colour (for example 桃花春水), the ink is
darkened along the sRGB ramp until it reaches the gate; the original four
colours are kept as the family and reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass

# name -> (label, {colour name: hex}, paper, ink, focus, support)
PAINTINGS: dict[str, tuple[str, dict[str, str], str, str, str, str]] = {
    "qinglv": (
        "青绿山水",
        {"石青": "#4E7E8C", "石绿": "#6E8F6A", "绢纸白": "#F5F0E6", "墨青": "#2E3E42"},
        "绢纸白",
        "墨青",
        "石青",
        "石绿",
    ),
    "yanlan": (
        "烟岚暮山",
        {"暮烟灰": "#8F8B83", "远山褐": "#8B6A55", "雾白": "#EEE7DB", "墨茶": "#43362F"},
        "雾白",
        "墨茶",
        "远山褐",
        "暮烟灰",
    ),
    "taohua": (
        "桃花春水",
        {"胭脂粉": "#D6A5AB", "春水青": "#A9C5C2", "绢云白": "#F7F3EC", "远岫灰": "#8F9690"},
        "绢云白",
        "远岫灰",
        "胭脂粉",
        "春水青",
    ),
    "hetang": (
        "荷塘清夏",
        {"荷叶碧": "#7E9A7D", "水纹青": "#A9C8C7", "藕粉": "#D8C1B7", "月白": "#F2F0EA"},
        "月白",
        "荷叶碧",
        "荷叶碧",
        "水纹青",
    ),
    "qiushan": (
        "秋山设色",
        {"赭石": "#A56A43", "枫褐": "#7B4A36", "米绢": "#EAD9BF", "松烟墨": "#38332E"},
        "米绢",
        "松烟墨",
        "赭石",
        "枫褐",
    ),
    "yebo": (
        "夜泊清辉",
        {"深蓝": "#25374A", "浅灰蓝": "#C8C9C5", "月白": "#ECE8DF", "近黑": "#20262B"},
        "月白",
        "近黑",
        "深蓝",
        "浅灰蓝",
    ),
    "xueyi": (
        "雪意寒林",
        {"雪绢白": "#F5F2EC", "冰灰": "#C9CDCF", "枯枝褐": "#76685A", "淡黛青": "#7A8B90"},
        "雪绢白",
        "枯枝褐",
        "淡黛青",
        "冰灰",
    ),
}

# The current course default (docs/配色规范.md).
EDITORIAL = {
    "paper": "#FBFAF7",
    "surface": "#F3F1EA",
    "ink": "#252A31",
    "body": "#2E3338",
    "muted": "#6B7280",
    "border": "#E3E0D7",
    "focus": "#E8733B",
    "input": "#4A82B8",
    "process": "#42A69A",
    "output": "#7A6FB0",
    "error": "#C75B55",
}


@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    paper: str
    ink: str
    focus: str
    support: str
    muted: str
    divider: str
    surface: str
    family: dict[str, str]

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "label": self.label,
            "paper": self.paper,
            "ink": self.ink,
            "focus": self.focus,
            "support": self.support,
            "muted": self.muted,
            "divider": self.divider,
            "surface": self.surface,
        }


def _rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = (_linear(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    a, b = luminance(foreground), luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def mix(first: str, second: str, amount: float) -> str:
    """Linear sRGB mix; ``amount`` 0 = first, 1 = second."""
    a, b = _rgb(first), _rgb(second)
    return _hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))  # type: ignore[arg-type]


def darken_until(color: str, background: str, target: float) -> str:
    """Mix toward black until the WCAG contrast against ``background`` is met."""
    result = color
    step = 0.0
    while contrast(result, background) < target and step < 0.95:
        step += 0.04
        result = mix(color, "#000000", step)
    return result


def lighten_until(color: str, background: str, target: float) -> str:
    result = color
    step = 0.0
    while contrast(result, background) < target and step < 0.95:
        step += 0.04
        result = mix(color, "#FFFFFF", step)
    return result


def _ensure_contrast(color: str, background: str, target: float) -> str:
    """Darken or lighten whichever direction reaches the gate first."""
    if contrast(color, background) >= target:
        return color
    dark = darken_until(color, background, target)
    light = lighten_until(color, background, target)
    return dark if contrast(dark, background) >= contrast(light, background) else light


def palette(key: str) -> Palette:
    """Resolve a palette key into accessible design roles."""
    if key == "editorial":
        tokens = EDITORIAL
        return Palette(
            key="editorial",
            label="Light Technical Editorial",
            paper=tokens["paper"],
            ink=tokens["ink"],
            # the brand orange sits at 2.9:1 on paper; the role is the accessible variant
            focus=_ensure_contrast(tokens["focus"], tokens["paper"], 3.0),
            support=_ensure_contrast(tokens["input"], tokens["paper"], 3.0),
            muted=_ensure_contrast(tokens["muted"], tokens["paper"], 4.5),
            divider=tokens["border"],
            surface=tokens["surface"],
            family={
                "focus": tokens["focus"],
                "input": tokens["input"],
                "process": tokens["process"],
                "output": tokens["output"],
                "error": tokens["error"],
            },
        )
    if key not in PAINTINGS:
        raise KeyError(f"unknown palette: {key} (choose from {sorted(keys())})")
    label, family, paper_name, ink_name, focus_name, support_name = PAINTINGS[key]
    paper = family[paper_name]
    ink = _ensure_contrast(family[ink_name], paper, 7.0)
    focus = _ensure_contrast(family[focus_name], paper, 3.0)
    support = _ensure_contrast(family[support_name], paper, 3.0)
    muted = _ensure_contrast(mix(ink, paper, 0.52), paper, 4.5)
    return Palette(
        key=key,
        label=label,
        paper=paper,
        ink=ink,
        focus=focus,
        support=support,
        muted=muted,
        divider=mix(ink, paper, 0.14),
        surface=mix(ink, paper, 0.05),
        family=family,
    )


def keys() -> list[str]:
    return ["editorial", *PAINTINGS.keys()]


def report(key: str) -> dict[str, object]:
    """Accessibility report used by the palette tests and the preview scene."""
    item = palette(key)
    return {
        "key": item.key,
        "label": item.label,
        "paper": item.paper,
        "ink": item.ink,
        "ink_contrast": round(contrast(item.ink, item.paper), 2),
        "focus": item.focus,
        "focus_contrast": round(contrast(item.focus, item.paper), 2),
        "support": item.support,
        "support_contrast": round(contrast(item.support, item.paper), 2),
        "muted": item.muted,
        "muted_contrast": round(contrast(item.muted, item.paper), 2),
        "family": item.family,
    }
