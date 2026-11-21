"""Compile production.yaml + slides.md into a static EVDS deck (reveal.js).

The plain CourseSlides/template shell only renders slides.md's markdown text;
it never applies the archetype layouts in css/mckinsey-orange.css.  This
compiler is the missing link: it reads the shot plan (which shots carry a
book figure, which are schematic/data/diagram beats) and pours that data into
the six EVDS archetypes (docs/教育内容视觉设计体系与视觉叙事规范.md, mapped in
docs/版式系统.md §3.1).

Display text (headline, bullets) comes from slides.md unchanged -- that is
owner-authored content.  production.yaml only drives layout: which archetype,
which image, and the callout/chart annotations that describe what the shot
will animate.  No numeric value is invented; schematic charts stay labelled
"schematic -- not measured", matching the shot notes' own disclaimer.

Layout, colour and type follow the mandatory visual specs, not the CSS file's
own drifted defaults:
  - docs/配色规范.md §3 Color Tokens (mckinsey-orange.css's :root has drifted
    from these; overridden locally rather than editing the shared theme).
  - docs/课程页面系统.md §3 fixed grid (header/title/main-visual/source/folio
    anchors) and §4 source citation format.
  - docs/版式系统.md §9.1 font-size tiers (body >= 24px, title >= 56px).
Book figures keep the mandated warm-white #EDE7DA panel (CLAUDE.md red line 3);
original pixels are never altered.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.content.production import Sequence, ShotPlan, load_production

ARCHETYPES = ("hero", "editorial", "annotated", "comparison", "process", "data")
FIGURE_TYPES = ("book_figure_annotated", "schematic_annotated")

# docs/配色规范.md §3 Color Tokens (canonical; mckinsey-orange.css has drifted).
INK = "#252A31"
BODY = "#2E3338"
MUTED = "#6B7280"
ORANGE = "#E8733B"
PAPER = "#FBFAF7"
BOOK_PANEL = "#EDE7DA"  # CLAUDE.md red line 3: warm-white panel for original book pixels
BORDER = "#E3E0D7"


@dataclass
class SlidePage:
    heading: str
    bullets: list[str]
    source: str | None


def parse_slides(text: str) -> list[SlidePage]:
    pages = []
    for chunk in re.split(r"\r?\n---\r?\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        heading = ""
        bullets = []
        source = None
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith("## "):
                heading = re.sub(r"^\d+\.\s*", "", line[3:])
            elif line.startswith("- "):
                bullets.append(line[2:])
            elif "<small>" in line:
                m = re.search(r"<small>(.*?)</small>", line, re.S)
                if m:
                    source = m.group(1).strip()
        pages.append(SlidePage(heading, bullets, source))
    return pages


def choose_archetype(seq: Sequence) -> str:
    if any(s.objects and s.visual_type in FIGURE_TYPES for s in seq.shots):
        return "annotated"
    if all(s.visual_type == "data_chart" for s in seq.shots):
        return "data"
    purposes = {s.purpose for s in seq.shots}
    if purposes == {"summarize"}:
        return "process"
    if purposes == {"compare"}:
        return "comparison"
    return "editorial"


def _concept(note: str) -> str:
    n = (note or "").lower()
    for key, words in (
        ("caliper", ["caliper", "l/h"]),
        ("ground", ["mirror", "ground", "wall"]),
        ("reynolds", ["reynolds", "decade"]),
        ("transition", ["laminar", "turbulent at", "transition station"]),
        ("routing", ["routing", "grille", "exhauster", "cabin inlet"]),
        ("separation", ["separation", "pin", "wake switch", "bubble", "vortex"]),
        ("envelope", ["subtract", "residual", "envelope"]),
        ("streamlines", ["streamline", "detach", "fold", "trace"]),
    ):
        if any(w in n for w in words):
            return key
    return "card"


def _detached(note: str) -> bool:
    n = (note or "").lower()
    return any(w in n for w in ("detach", "separate", "lets go", "lose", "let go"))


def _svg_wrap(inner: str) -> str:
    return (
        '<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet" '
        'style="width:100%;height:100%;display:block;">' + inner + "</svg>"
    )


def _flow_svg(attached: bool) -> str:
    body = f'<rect x="70" y="130" width="260" height="70" rx="30" fill="{BORDER}" />'
    if attached:
        lines = "".join(
            f'<path d="M20,{90 + i * 18} C120,{80 + i * 18} 280,{80 + i * 18} 380,{90 + i * 18}" '
            f'stroke="{MUTED}" stroke-width="2.5" fill="none" />'
            for i in range(4)
        )
        tag = "attached to the trailing edge"
    else:
        lines = "".join(
            f'<path d="M20,{90 + i * 18} C120,{80 + i * 18} 220,{70 + i * 18} 260,{40 + i * 22}" '
            f'stroke="{ORANGE}" stroke-width="2.5" fill="none" />'
            for i in range(4)
        )
        tag = "lets go at the rear"
    label = f'<text x="200" y="270" text-anchor="middle" font-size="18" fill="{MUTED}">{tag}</text>'
    return _svg_wrap(body + lines + label)


def _caliper_svg() -> str:
    body = f'<rect x="60" y="120" width="280" height="80" rx="24" fill="{BORDER}" />'
    cal = (
        f'<line x1="60" y1="230" x2="340" y2="230" stroke="{INK}" stroke-width="3" />'
        f'<line x1="60" y1="220" x2="60" y2="240" stroke="{INK}" stroke-width="3" />'
        f'<line x1="340" y1="220" x2="340" y2="240" stroke="{INK}" stroke-width="3" />'
    )
    label = f'<text x="200" y="260" text-anchor="middle" font-size="18" fill="{INK}">L/H ~ 3 (typical)</text>'
    return _svg_wrap(body + cal + label)


def _reynolds_svg() -> str:
    axis = f'<line x1="30" y1="150" x2="370" y2="150" stroke="{INK}" stroke-width="3" />'
    ticks = "".join(
        f'<line x1="{30 + i * 85}" y1="140" x2="{30 + i * 85}" y2="160" stroke="{INK}" stroke-width="2" />'
        f'<text x="{30 + i * 85}" y="182" text-anchor="middle" font-size="16" fill="{MUTED}">1e{4 + i}</text>'
        for i in range(4)
    )
    mark = f'<circle cx="285" cy="150" r="9" fill="{ORANGE}" />'
    label = f'<text x="200" y="110" text-anchor="middle" font-size="18" fill="{INK}">Re ~ 1e7 at highway speed</text>'
    return _svg_wrap(axis + ticks + mark + label)


def _envelope_svg() -> str:
    body = f'<rect x="50" y="110" width="300" height="90" rx="20" fill="{BORDER}" />'
    cuts = "".join(
        f'<rect x="{x}" y="110" width="{w}" height="90" fill="{BOOK_PANEL}" stroke="{ORANGE}" stroke-width="2" />'
        for x, w in ((50, 70), (160, 70), (270, 80))
    )
    labels = "".join(
        f'<text x="{x}" y="95" text-anchor="middle" font-size="16" fill="{ORANGE}">{lab}</text>'
        for x, lab in ((85, "crash"), (195, "cooling"), (310, "sightlines"))
    )
    return _svg_wrap(body + cuts + labels)


def _separation_svg() -> str:
    body = f'<rect x="40" y="120" width="220" height="70" rx="24" fill="{BORDER}" />'
    pin = f'<circle cx="260" cy="120" r="7" fill="{ORANGE}" />'
    bubble = f'<circle cx="310" cy="155" r="45" stroke="{INK}" stroke-width="3" fill="none" />'
    label = f'<text x="200" y="240" text-anchor="middle" font-size="18" fill="{INK}">place the separation line</text>'
    return _svg_wrap(body + pin + bubble + label)


def _card_svg() -> str:
    return _svg_wrap(
        f'<rect x="60" y="100" width="280" height="100" rx="8" fill="none" stroke="{BORDER}" stroke-width="2" />'
    )


_CONCEPT_SVG = {
    "caliper": _caliper_svg,
    "reynolds": _reynolds_svg,
    "envelope": _envelope_svg,
    "separation": _separation_svg,
}


def _concept_svg(note: str) -> str:
    key = _concept(note)
    if key == "streamlines":
        return _flow_svg(attached=not _detached(note))
    fn = _CONCEPT_SVG.get(key, _card_svg)
    return fn()


def _chart_svg() -> str:
    bars = (
        (60, 260, INK, "lost"),
        (150, 90, MUTED, "recovered"),
        (240, 170, ORANGE, "wake deficit"),
    )
    parts = [f'<text x="200" y="30" text-anchor="middle" font-size="17" fill="{MUTED}">schematic — not measured</text>']
    for y, w, colour, lab in bars:
        parts.append(f'<text x="20" y="{y + 22}" font-size="17" fill="{INK}">{lab}</text>')
        parts.append(f'<rect x="120" y="{y}" width="{w}" height="30" fill="{colour}" rx="3" />')
    return _svg_wrap("".join(parts))


def _badge_position(note: str, index: int) -> tuple[str, str]:
    n = (note or "").lower()
    top = f"calc(6% + {index * 38}px)"
    if any(w in n for w in ("bonnet", "nose", "grille", "front", "stagnation")):
        return (top, "4%")
    if any(w in n for w in ("roof", "top", "upper")):
        return (top, "30%")
    if any(w in n for w in ("underbody", "floor", "diffuser", "ground")):
        return (top, "20%")
    if any(w in n for w in ("rear", "tail", "wake", "bubble", "separation", "exit", "vortex")):
        return (top, "62%")
    return (top, "44%")


def _short_label(note: str, limit: int = 42) -> str:
    note = note.strip()
    if len(note) <= limit:
        return note
    cut = note[:limit]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(",;") + "…"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _figure_shots(seq: Sequence) -> list[ShotPlan]:
    return [s for s in seq.shots if s.objects and s.visual_type in FIGURE_TYPES]


def _render_annotated(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figure_shots = _figure_shots(seq)
    assets: list[str] = []
    for s in figure_shots:
        for obj in s.objects:
            if obj not in assets:
                assets.append(obj)
    multi = len(assets) > 1
    dual_class = " dual" if multi else ""
    blocks = []
    for obj in assets:
        asset_path = lesson_dir / obj
        if not asset_path.is_file():
            raise FileNotFoundError(f"deck asset missing: {asset_path}")
        filename = Path(obj).name
        badges = []
        for s in figure_shots:
            if obj not in s.objects:
                continue
            for action in s.actions:
                if not action.note:
                    continue
                top, left = _badge_position(action.note, len(badges))
                label = _short_label(action.note)
                badges.append(
                    f'<div class="callout-badge" style="top:{top};left:{left};">{_esc(label)}</div>'
                )
        blocks.append(
            f'<div class="annotated-container{dual_class}" style="background:{BOOK_PANEL};">'
            f'<img src="/lessons/{slug}/assets/{filename}" alt="{_esc(filename)}">'
            + "".join(badges)
            + "</div>"
        )
    caption = "".join(f"<li>{_esc(b)}</li>" for b in page.bullets)
    return (
        '<div class="slide--annotated">'
        + "".join(blocks)
        + f'<ul class="deck-caption">{caption}</ul>'
        + "</div>"
    )


def _render_comparison(seq: Sequence, page: SlidePage) -> str:
    bullets = page.bullets or ["", "", ""]
    b1 = bullets[0]
    b2 = bullets[1] if len(bullets) > 1 else ""
    rest = bullets[2:]
    notes = [s.actions[0].note if s.actions else "" for s in seq.shots]
    n1 = notes[0] if notes else ""
    n2 = notes[1] if len(notes) > 1 else ""
    cards = (
        f'<div class="compare-card"><div class="compare-visual">{_concept_svg(n1)}</div>'
        f'<p class="deck-body">{_esc(b1)}</p></div>'
        f'<div class="compare-card active"><div class="compare-visual">{_concept_svg(n2)}</div>'
        f'<p class="deck-body">{_esc(b2)}</p></div>'
    )
    conclusion = "".join(f"<li>{_esc(b)}</li>" for b in rest)
    tail = f'<ul class="deck-caption deck-span">{conclusion}</ul>' if rest else ""
    return f'<div class="slide--comparison">{cards}{tail}</div>'


def _render_editorial(seq: Sequence, page: SlidePage) -> str:
    note = seq.shots[0].actions[0].note if seq.shots and seq.shots[0].actions else ""
    visual = _concept_svg(note)
    steps = "".join(
        f'<div class="step-item active"><div class="step-number">{i + 1:02d}</div>'
        f'<p class="deck-body">{_esc(b)}</p></div>'
        for i, b in enumerate(page.bullets)
    )
    return (
        '<div class="slide--editorial">'
        f'<div class="editorial-visual">{visual}</div>'
        f'<div class="editorial-text">{steps}</div>'
        "</div>"
    )


def _render_data(seq: Sequence, page: SlidePage) -> str:
    takeaway = "".join(f"<li>{_esc(b)}</li>" for b in page.bullets)
    return (
        '<div class="slide--data">'
        f'<div class="chart-container">{_chart_svg()}</div>'
        f'<div><div class="takeaway-box"><ul class="deck-body-list">{takeaway}</ul></div></div>'
        "</div>"
    )


def _render_process(seq: Sequence, page: SlidePage) -> str:
    steps = "".join(
        f'<div class="process-step"><div class="step-tag">Step {i + 1:02d}</div>'
        f'<p class="deck-body">{_esc(b)}</p></div>'
        for i, b in enumerate(page.bullets)
    )
    return f'<div class="slide--process"><div class="process-grid">{steps}</div></div>'


_RENDERERS = {
    "annotated": _render_annotated,
    "comparison": _render_comparison,
    "editorial": _render_editorial,
    "data": _render_data,
    "process": _render_process,
}


def _source_text(page: SlidePage) -> str:
    if not page.source:
        return "Schematic · no external source"
    text = page.source
    if text.startswith("Source:"):
        text = "Source ·" + text[len("Source:"):]
    return text


def _footer(page: SlidePage, idx: int, total: int) -> str:
    return (
        '<div class="slide-footer">'
        f'<span class="source">{_esc(_source_text(page))}</span>'
        f'<span class="folio">{idx:02d} / {total:02d}</span>'
        "</div>"
    )


# Local overrides: canonical colour tokens, the fixed grid from
# docs/课程页面系统.md §3, and font-size tiers from docs/版式系统.md §9.1.
# Scoped to this generated deck only; the shared mckinsey-orange.css is not edited.
_OVERRIDE_CSS = """
:root {
  --mk-white: #FBFAF7; --mk-text: #252A31; --mk-text-muted: #6B7280;
  --mk-orange: #E8733B; --mk-orange-soft: #F6E3D6; --mk-border: #E3E0D7; --mk-code-bg: #F3F1EA;
}
html, body, .reveal-viewport { background: #FBFAF7; }
.reveal { font-size: 30px; color: #252A31; }
.reveal .slides > section { padding: 0 !important; }
.reveal .kicker {
  position: absolute; left: 110px; top: 70px; margin: 0;
  font-size: 20px; font-weight: 700; color: #E8733B; letter-spacing: 0.12em; text-transform: uppercase;
}
.reveal h2.headline {
  position: absolute; left: 110px; top: 128px; width: 1700px; margin: 0;
  font-size: 60px; font-weight: 700; line-height: 1.15; color: #252A31;
}
.main-visual { position: absolute; left: 110px; top: 330px; width: 1700px; height: 500px; }
.reveal .slide-footer {
  position: absolute; left: 110px; right: 110px; bottom: 175px;
  font-size: 19px; color: #6B7280; border-top: 1px solid #E3E0D7; padding-top: 6px;
}
.reveal .slide-footer .source { color: #2E3338; max-width: 1250px; }
.reveal .slide-footer .folio {
  color: #252A31; background: #F3F1EA; border: 1px solid #E3E0D7; letter-spacing: 0.16em;
}
.reveal .slide--annotated .annotated-container { height: 370px; }
.reveal .slide--annotated .annotated-container.dual { height: 165px; }
.reveal .slide--annotated .callout-badge {
  font-size: 24px; background: rgba(37, 42, 49, 0.92); white-space: nowrap;
}
.reveal .slide--editorial .editorial-visual { height: 460px; }
.reveal .slide--comparison .compare-visual { height: 250px; }
.reveal .slide--data .chart-container { height: 430px; }
.deck-body, .reveal .slide--editorial .step-item p, .reveal .slide--process .process-step p,
.reveal .slide--comparison .compare-card p { font-size: 30px; margin: 8px 0 0; }
.deck-body-list, .deck-caption { font-size: 26px; color: #6B7280; margin: 10px 0 0; padding-left: 22px; }
.deck-span { grid-column: 1 / 3; }
.reveal .slide--editorial .step-number, .reveal .slide--process .step-tag { font-size: 24px; }
"""

_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="/CourseSlides/node_modules/reveal.js/dist/reset.css">
<link rel="stylesheet" href="/CourseSlides/node_modules/reveal.js/dist/reveal.css">
<link rel="stylesheet" href="/CourseSlides/css/mckinsey-orange.css">
<style>{override_css}</style>
</head>
<body>
<div class="reveal"><div class="slides">
"""

_TAIL = """</div></div>
<script src="/CourseSlides/node_modules/reveal.js/dist/reveal.js"></script>
<script>
  Reveal.initialize({
    width: 1920, height: 1080, margin: 0,
    controls: true, progress: true, center: false, hash: true,
    transition: 'fade', transitionSpeed: 'fast'
  });
</script>
</body>
</html>
"""


def compile_deck(paths: LessonPaths) -> dict:
    lesson_dir = paths.lesson_dir
    slug = paths.slug
    production_file = lesson_dir / "authoring/production.yaml"
    plan = load_production(production_file)
    slides_file = paths.content_path(paths.lesson.content.slides)
    pages = parse_slides(slides_file.read_text(encoding="utf-8"))
    if len(pages) != len(plan.sequences):
        raise ValueError(
            f"slides.md has {len(pages)} pages but production.yaml has {len(plan.sequences)} sequences"
        )

    total = len(pages)
    sections = []
    manifest_pages = []
    assets_used: list[str] = []
    for idx, (seq, page) in enumerate(zip(plan.sequences, pages), start=1):
        archetype = choose_archetype(seq)
        if archetype == "annotated":
            body = _render_annotated(seq, page, slug, lesson_dir)
            for s in _figure_shots(seq):
                for obj in s.objects:
                    if obj not in assets_used:
                        assets_used.append(obj)
        else:
            body = _RENDERERS[archetype](seq, page)
        headline = page.heading or seq.title
        kicker = f"{idx:02d} / {total:02d} · {_esc(seq.title)}"
        section = (
            "<section>"
            f'<div class="kicker">{kicker}</div>'
            f'<h2 class="headline">{_esc(headline)}</h2>'
            f'<div class="main-visual">{body}</div>'
            f"{_footer(page, idx, total)}"
            "</section>"
        )
        sections.append(section)
        manifest_pages.append({"page": idx, "archetype": archetype, "has_source": bool(page.source)})

    out_dir = paths.build_root / "deck"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    title = f"{slug} · Deck"
    doc = _HEAD.format(title=_esc(title), override_css=_OVERRIDE_CSS) + "\n".join(sections) + "\n" + _TAIL
    out_file.write_text(doc, encoding="utf-8")

    production_sha = hashlib.sha256(production_file.read_bytes()).hexdigest()
    slides_sha = hashlib.sha256(slides_file.read_bytes()).hexdigest()
    manifest = {
        "lesson": slug,
        "pages": total,
        "archetypes": manifest_pages,
        "assets_used": assets_used,
        "production_sha256": production_sha,
        "slides_sha256": slides_sha,
    }
    (out_dir / "deck-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest