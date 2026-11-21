"""Compile production.yaml + slides.md into a static EVDS deck (reveal.js).

Figure-driven, reuse-first (CLAUDE.md A1/A2/A4): every page's main visual is a
real illustration -- an original book figure (warm-white #EDE7DA panel, pixels
untouched) or an owner-designated study-aid supplement (assets/baseline-*.png,
white figure panel).  No hand-drawn SVG mechanism is ever emitted (red line A4);
the only SVG is the data page's chart, rebuilt to scale from canonical numbers
with a labelled 0-100% axis (red line A6).

Display text (headline, bullets) comes from slides.md unchanged -- owner content.
production.yaml drives layout only: archetype, which figures (shot ``objects``),
and nothing else.  Director instructions (shot action notes) never reach the
screen; they belong to the animation layer.

Layout follows the open-design golden-board benchmark and the mandatory specs:
kicker (orange caps) / headline with orange rule / large figure / source bottom
left / folio bottom right; EVDS archetype class on the <section> (E6 contract).
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.content.production import Sequence, ShotPlan, load_production

ARCHETYPES = ("hero", "editorial", "annotated", "comparison", "process", "data")
BOOK_FIGURE = "book_figure_annotated"
SUPPLEMENT_PREFIX = "assets/baseline-"

# docs/配色规范.md §3 canonical tokens (mckinsey-orange.css :root has drifted).
INK = "#252A31"
BODY = "#2E3338"
MUTED = "#6B7280"
ORANGE = "#E8733B"
PAPER = "#FBFAF7"
BOOK_PANEL = "#EDE7DA"  # red line 3: warm-white panel for original book pixels
BORDER = "#E3E0D7"

NBLM_CREDIT = (
    "Illustration · NotebookLM study aid after Hucho, Aerodynamics of Road Vehicles"
)
CHART_CREDIT = (
    "Chart · NotebookLM study aid after Hucho, Aerodynamics of Road Vehicles, Ch. 1"
)
# Full credits (with edition / mapping notes) are preserved off-screen in the
# citation provenance sidecar; the on-screen line stays single-line and compact.
FULL_NBLM_CREDIT = (
    "Illustration · NotebookLM study aid after Hucho, "
    "Aerodynamics of Road Vehicles, 5th ed."
)
FULL_CHART_CREDIT = (
    "Chart redrawn to scale · NotebookLM study aid after Hucho, "
    "Aerodynamics of Road Vehicles, 5th ed., Ch. 1"
)
# Page-mapping notes are evidence, not screen text: stripped from the display
# line and recorded in the provenance sidecar.
MAPPING_NOTE = re.compile(r"\s*·?\s*printed page\s*=\s*PDF page\s*[−-]\s*\d+", re.I)

# Local OFL faces (content-root references/fonts, manifest-verified).  Compiled
# into build/<slug>/deck/fonts and referenced relatively; a missing file is a
# hard error, never a silent fallback to a system/CDN font.
FONT_SOURCES = {
    "inter": ("inter/Inter-var.ttf", "Inter"),
    "sourcesans3": ("sourcesans3/SourceSans3-var.ttf", "Source Sans 3"),
}
SYSTEM_STACK = "Inter, Helvetica, Arial, sans-serif"

# Debug-phase display titles (English screen text, red line B7).  At template
# freeze these are driven from the COURSE_MAP canonical episode titles.
DISPLAY_TITLE = {
    "t1-01-why-aerodynamics": "Why a car is fundamentally a bluff-body flow problem",
}
HERO_KICKER = "T1-01 · The Bluff-Body Paradigm"

# Canonical automotive drag breakdown (shared course data, not per-lesson invention).
DRAG_SEGMENTS = (
    (75.0, "70–80%", "Pressure / Form drag", ORANGE),
    (12.5, "10–15%", "Friction drag", MUTED),
    (10.0, "8–12%", "Internal / Cooling", BORDER),
)


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
    if any(s.objects and s.visual_type == BOOK_FIGURE for s in seq.shots):
        return "annotated"
    if all(s.visual_type == "data_chart" for s in seq.shots):
        return "data"
    purposes = {s.purpose for s in seq.shots}
    if purposes == {"summarize"}:
        return "process"
    if purposes == {"compare"}:
        return "comparison"
    return "editorial"


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _figures(seq: Sequence) -> list[tuple[str, bool]]:
    """(object path, is_book) in shot order, deduped.

    baseline-* (study-aid mattes) and flow-* (region crops of the study-aid
    three-systems diagram) are supplements, not original book pixels.
    """
    out: list[tuple[str, bool]] = []
    for shot in seq.shots:
        for obj in shot.objects:
            if obj not in [o for o, _ in out]:
                is_book = not (obj.startswith(SUPPLEMENT_PREFIX) or obj.startswith("assets/flow-"))
                out.append((obj, is_book))
    return out


def _img_panel(obj: str, is_book: bool, slug: str, lesson_dir: Path, cls: str) -> str:
    path = lesson_dir / obj
    if not path.is_file():
        raise FileNotFoundError(f"deck asset missing: {path}")
    name = Path(obj).name
    bg = BOOK_PANEL if is_book else "#FFFFFF"
    return (
        f'<div class="figure-panel {cls}" style="background:{bg};">'
        f'<img src="/lessons/{slug}/assets/{name}" alt="{_esc(name)}">'
        "</div>"
    )


def _caption(bullets: list[str], cls: str = "deck-caption") -> str:
    if not bullets:
        return ""
    items = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
    return f'<ul class="{cls}">{items}</ul>'


def _render_hero(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figs = _figures(seq)
    panels = "".join(
        _img_panel(obj, is_book, slug, lesson_dir, "hero-figure" if i == 0 else "hero-strip")
        for i, (obj, is_book) in enumerate(figs)
    )
    return f'<div class="hero-stack">{panels}{_caption(page.bullets)}</div>'


def _render_annotated(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figs = _figures(seq)
    multi = len(figs) > 1
    panels = "".join(
        _img_panel(obj, is_book, slug, lesson_dir, "ann-figure" + (" dual" if multi else ""))
        for obj, is_book in figs
    )
    return f'<div class="ann-stack">{panels}{_caption(page.bullets)}</div>'


def _render_comparison(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figs = _figures(seq)
    panel = _img_panel(figs[0][0], figs[0][1], slug, lesson_dir, "compare-figure") if figs else ""
    b = page.bullets or ["", ""]
    cards = (
        f'<div class="compare-card"><p class="deck-body">{_esc(b[0])}</p></div>'
        f'<div class="compare-card active"><p class="deck-body">{_esc(b[1] if len(b) > 1 else "")}</p></div>'
    )
    return f'<div class="compare-stack">{panel}<div class="compare-row">{cards}</div>{_caption(page.bullets[2:])}</div>'


def _render_editorial(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figs = _figures(seq)
    panel = _img_panel(figs[0][0], figs[0][1], slug, lesson_dir, "edit-figure") if figs else ""
    steps = "".join(
        f'<div class="step-item"><div class="step-number">{i + 1:02d}</div>'
        f'<p class="deck-body">{_esc(b)}</p></div>'
        for i, b in enumerate(page.bullets)
    )
    return f'<div class="edit-grid"><div class="edit-text">{steps}</div>{panel}</div>'


def _chart_svg() -> str:
    """Data chart rebuilt to scale from canonical numbers, labelled 0-100% axis.

    Narrow segments carry no inside text (it would collide); a swatch legend
    below the axis names every segment with its range, so nothing overlaps.
    """
    parts = ['<svg viewBox="0 0 900 500" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;display:block;">']
    x0, x1, y, h = 40, 860, 60, 110
    cursor = x0
    for i, (frac, lab, name, colour) in enumerate(DRAG_SEGMENTS):
        w = (x1 - x0) * frac / 100.0
        parts.append(f'<rect x="{cursor:.1f}" y="{y}" width="{w:.1f}" height="{h}" fill="{colour}" />')
        if i == 0:
            parts.append(
                f'<text x="{cursor + w / 2:.1f}" y="{y + h / 2 - 4}" text-anchor="middle" '
                f'font-size="34" font-weight="700" fill="#FFFFFF">{lab}</text>'
            )
            parts.append(
                f'<text x="{cursor + w / 2:.1f}" y="{y + h / 2 + 34}" text-anchor="middle" '
                f'font-size="24" fill="#FFFFFF">{name}</text>'
            )
        cursor += w
    axis_y = y + h + 34
    parts.append(f'<line x1="{x0}" y1="{axis_y}" x2="{x1}" y2="{axis_y}" stroke="{INK}" stroke-width="3" />')
    for tick in (0, 25, 50, 75, 100):
        tx = x0 + (x1 - x0) * tick / 100.0
        parts.append(f'<line x1="{tx:.1f}" y1="{axis_y - 8}" x2="{tx:.1f}" y2="{axis_y + 8}" stroke="{INK}" stroke-width="2" />')
        parts.append(f'<text x="{tx:.1f}" y="{axis_y + 40}" text-anchor="middle" font-size="24" fill="{MUTED}">{tick}%</text>')
    ly = axis_y + 86
    for frac, lab, name, colour in DRAG_SEGMENTS:
        parts.append(f'<rect x="{x0}" y="{ly - 20}" width="26" height="26" fill="{colour}" />')
        parts.append(f'<text x="{x0 + 40}" y="{ly}" font-size="25" fill="{BODY}">{lab}  {name}</text>')
        ly += 44
    parts.append(
        f'<text x="{x0}" y="{ly + 16}" font-size="25" fill="{BODY}">'
        "Passenger car Cd 0.25–0.40 · streamlined body ~0.05</text>"
    )
    parts.append(
        f'<text x="{x0}" y="{ly + 52}" font-size="25" fill="{BODY}">'
        "Cooling alone ~10% of total aerodynamic drag</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def _render_data(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    takeaway = _caption(page.bullets, "deck-body-list")
    return (
        '<div class="data-grid">'
        f'<div class="chart-container">{_chart_svg()}</div>'
        f'<div class="takeaway-box">{takeaway}</div>'
        "</div>"
    )


def _render_process(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path) -> str:
    figs = _figures(seq)
    panel = _img_panel(figs[0][0], figs[0][1], slug, lesson_dir, "process-figure") if figs else ""
    steps = "".join(
        f'<div class="process-step"><div class="step-tag">Step {i + 1:02d}</div>'
        f'<p class="deck-body">{_esc(b)}</p></div>'
        for i, b in enumerate(page.bullets)
    )
    return f'<div class="process-stack">{panel}<div class="process-grid">{steps}</div></div>'


_RENDERERS = {
    "hero": _render_hero,
    "annotated": _render_annotated,
    "comparison": _render_comparison,
    "editorial": _render_editorial,
    "data": _render_data,
    "process": _render_process,
}


# --- P0 composition pilots (pages 1/2/3/7).  Owner approves the composition
# system on these four before the remaining pages are batched.  Figures are
# swapped by source only (book hi-res / approved supplements); nothing redrawn.

def _render_p01(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path,
                pages: list[SlidePage] | None = None) -> str:
    figs = _figures(seq)
    main = next((o for o, _ in figs if "aircraft-vs-automobile" in o), figs[0][0] if figs else "")
    panel = _img_panel(main, False, slug, lesson_dir, "p01-main") if main else ""
    b = page.bullets or ["", "", ""]
    cards = (
        '<div class="p01-card"><span class="p01-tag">Streamlined · attached</span>'
        f'<p class="deck-body">{_esc(b[0])}</p></div>'
        '<div class="p01-card active"><span class="p01-tag">Bluff · separated</span>'
        f'<p class="deck-body">{_esc(b[1] if len(b) > 1 else "")}</p></div>'
    )
    key = b[2] if len(b) > 2 else ""
    idea = f"{key} — manage separation and the wake, not just guide the flow." if key else \
        "Manage separation and the wake, not just guide the flow."
    return (
        '<div class="p01-stack">'
        f'{panel}<div class="p01-cards">{cards}</div>'
        f'<div class="key-idea"><span class="key-tag">Key idea</span>{_esc(idea)}</div>'
        "</div>"
    )


def _render_p02(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path,
                pages: list[SlidePage] | None = None) -> str:
    figs = _figures(seq)
    panel = _img_panel(figs[0][0], True, slug, lesson_dir, "p02-fig") if figs else ""
    notes = "".join(
        f'<li class="{"hot" if i == 2 else ""}"><span class="note-num">{i + 1:02d}</span>'
        f'<p class="deck-body">{_esc(b)}</p></li>'
        for i, b in enumerate(page.bullets[:3])
    )
    return f'<div class="p02-grid">{panel}<ol class="p02-notes">{notes}</ol></div>'


def _render_p03(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path,
                pages: list[SlidePage] | None = None) -> str:
    left = "assets/book-hi-fig-1.4a.png"
    right = "assets/book-hi-fig-1.4b.png"
    lp = _img_panel(left, True, slug, lesson_dir, "p03-fig")
    rp = _img_panel(right, True, slug, lesson_dir, "p03-fig")
    b = page.bullets or ["", ""]
    exp_caption = ""
    if pages and len(pages) > 1 and len(pages[1].bullets) > 1:
        exp_caption = pages[1].bullets[1]
    return (
        '<div class="p03-grid">'
        f'<div class="p03-col"><span class="p03-label">Experiment</span>{lp}'
        f'<p class="deck-caption-line">{_esc(exp_caption)}</p></div>'
        '<div class="p03-mid"><p class="p03-relation">Compare the separation point</p>'
        '<p class="p03-confidence">Agreement, under proper validation, strengthens confidence.</p></div>'
        f'<div class="p03-col"><span class="p03-label">Computation</span>{rp}'
        f'<p class="deck-caption-line">{_esc(b[0])}</p></div>'
        "</div>"
    )


def _render_p07(seq: Sequence, page: SlidePage, slug: str, lesson_dir: Path,
                pages: list[SlidePage] | None = None) -> str:
    figs = [o for o, _ in _figures(seq)]
    order = ["flow-external", "flow-cooling", "flow-cabin"]
    picks = [next((o for o in figs if k in o), "") for k in order]
    titles = ["External flow", "Engine-bay cooling", "Cabin ventilation"]
    lines = [
        page.bullets[0] if page.bullets else "",
        "Through the body: cooling",
        "Through the body: cabin",
    ]
    cols = "".join(
        f'<div class="p07-col"><div class="figure-panel p07-fig">'
        f'<img src="/lessons/{slug}/assets/{Path(o).name}" alt="{_esc(Path(o).name)}"></div>'
        f'<div class="p07-head"><span class="note-num">{i + 1:02d}</span>'
        f'<span class="p07-title">{_esc(t)}</span></div>'
        f'<p class="deck-body">{_esc(l)}</p></div>'
        for i, (o, t, l) in enumerate(zip(picks, titles, lines)) if o
    )
    scope = page.bullets[2] if len(page.bullets) > 2 else ""
    summary = ("A vehicle is not a solid aerodynamic object. Air flows around it, through it, and inside it.")
    return (
        f'<div class="p07-stack"><div class="p07-grid">{cols}</div>'
        f'<p class="p07-scope">{_esc(scope)}</p>'
        f'<div class="key-idea"><span class="key-tag">Summary</span>{_esc(summary)}</div></div>'
    )


P0_LAYOUTS = {1: _render_p01, 2: _render_p02, 3: _render_p03, 7: _render_p07}

# Verified book citations (figure/page checked against the book PDF, printed
# page 5 = PDF page 26, Figure 1.4, photo/figure Daimler AG).  The slides.md
# page mapping was wrong; the correction is recorded in the provenance sidecar.
VERIFIED_BOOK_SOURCE = {
    ("t1-01-why-aerodynamics", 2): "Source · Aerodynamics of Road Vehicles, Fig. 1.4a, p. 5 · Photo: Daimler AG",
    ("t1-01-why-aerodynamics", 3): "Source · Aerodynamics of Road Vehicles, Fig. 1.4a–b, p. 5 · Photo: Daimler AG",
}
VERIFIED_BOOK_FULL = {
    ("t1-01-why-aerodynamics", 2): "Source · Aerodynamics of Road Vehicles, 5th ed., Fig. 1.4a, p. 5 · Photo: Daimler AG",
    ("t1-01-why-aerodynamics", 3): "Source · Aerodynamics of Road Vehicles, 5th ed., Fig. 1.4a–b, p. 5 · Photo/figure: Daimler AG",
}


def _display_source(text: str) -> str:
    """On-screen citation: single line, mapping notes moved to provenance."""
    return MAPPING_NOTE.sub("", text).strip().rstrip("·").strip()


def _source_text(page: SlidePage, seq: Sequence, archetype: str, idx: int | None = None, slug: str | None = None) -> str:
    if (slug, idx) in VERIFIED_BOOK_SOURCE:
        return VERIFIED_BOOK_SOURCE[(slug, idx)]
    figs = _figures(seq)
    has_book = any(is_book for _, is_book in figs)
    if has_book and page.source:
        text = page.source
        if text.startswith("Source:"):
            text = "Source ·" + text[len("Source:"):]
        return _display_source(text)
    if archetype == "data":
        return CHART_CREDIT
    if figs:
        return NBLM_CREDIT
    return "Schematic · no external source"


def _full_source(page: SlidePage, seq: Sequence, archetype: str, idx: int | None = None, slug: str | None = None) -> str:
    if (slug, idx) in VERIFIED_BOOK_FULL:
        return VERIFIED_BOOK_FULL[(slug, idx)]
    figs = _figures(seq)
    has_book = any(is_book for _, is_book in figs)
    if has_book and page.source:
        text = page.source
        if text.startswith("Source:"):
            text = "Source ·" + text[len("Source:"):]
        return text
    if archetype == "data":
        return FULL_CHART_CREDIT
    if figs:
        return FULL_NBLM_CREDIT
    return "Schematic · no external source"


def _footer(page: SlidePage, seq: Sequence, archetype: str, idx: int, total: int, slug: str | None = None) -> str:
    return (
        '<div class="slide-footer">'
        f'<span class="source">{_esc(_source_text(page, seq, archetype, idx, slug))}</span>'
        f'<span class="folio">{idx:02d} / {total:02d}</span>'
        "</div>"
    )


_OVERRIDE_CSS = """
__FACE_CSS__
:root {
  --mk-white: #FBFAF7; --mk-text: #252A31; --mk-text-muted: #6B7280;
  --mk-orange: #E8733B; --mk-orange-soft: #F6E3D6; --mk-border: #E3E0D7; --mk-code-bg: #F3F1EA;
}
html, body, .reveal-viewport { background: #FBFAF7; }
.reveal { font-size: 30px; color: #252A31; font-family: __FONT_STACK__; }
.reveal .slides > section { padding: 0 !important; text-align: left; }
.reveal .kicker {
  position: absolute; left: 110px; top: 70px; margin: 0;
  font-family: __FONT_STACK__;
  font-size: 21px; font-weight: 700; color: #E8733B; letter-spacing: 0.14em; text-transform: uppercase;
}
.reveal h2.headline {
  position: absolute; left: 110px; top: 122px; width: 1700px; margin: 0;
  font-family: __FONT_STACK__;
  font-size: 62px; font-weight: 700; line-height: 1.12; color: #252A31;
}
.reveal h2.headline::after {
  content: ""; display: block; width: 220px; height: 4px; background: #E8733B; margin-top: 18px;
}
.main-visual { position: absolute; left: 110px; top: 320px; width: 1700px; height: 510px; }
/* Source sits in the true bottom-left corner (left 60 / bottom 48), width-capped
   so it never reaches the centered low_center subtitle column (x>=580); folio
   holds the bottom-right.  No full-width rule: it would read as a content
   divider and crowd the body.  Body main-visual ends at y830; source top stays
   below y880. */
.reveal .slide-footer {
  position: absolute; left: 60px; right: 60px; bottom: 48px;
  font-family: __FONT_STACK__;
  font-size: 15px; color: #6B7280;
}
.reveal .slide-footer .source {
  position: absolute; left: 0; bottom: 0; max-width: 560px;
  color: #2E3338; font-size: 15px; line-height: 1.3;
  font-family: __FONT_STACK__; letter-spacing: -0.01em; white-space: nowrap;
}
.reveal .slide-footer .folio {
  position: absolute; right: 0; bottom: 0;
  color: #E8733B; font-weight: 700; letter-spacing: 0.16em; white-space: nowrap; font-size: 15px;
}
.figure-panel {
  border: 1px solid #E3E0D7; box-shadow: 0 4px 18px rgba(37,42,49,.08);
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.figure-panel img { width: 100%; height: 100%; object-fit: contain; display: block; }
.deck-body { font-size: 30px; line-height: 1.4; color: #2E3338; margin: 0; }
.deck-caption, .deck-body-list { list-style: none; margin: 14px 0 0; padding: 0; }
.deck-caption li, .deck-body-list li {
  font-size: 27px; line-height: 1.45; color: #2E3338; margin: 0 0 10px; padding-left: 30px; position: relative;
}
.deck-caption li::before, .deck-body-list li::before {
  content: ""; position: absolute; left: 0; top: 12px; width: 12px; height: 12px; background: #E8733B;
}
.hero-stack { display: flex; flex-direction: column; gap: 16px; height: 100%; }
.hero-figure { height: 280px; }
.hero-strip { height: 170px; }
.hero-stack .deck-caption { display: flex; gap: 48px; margin: 0; }
.hero-stack .deck-caption li { margin: 0; }
.ann-stack { display: flex; flex-direction: column; gap: 14px; height: 100%; }
.ann-figure { height: 380px; }
.ann-figure.dual { height: 180px; }
.compare-stack { display: flex; flex-direction: column; gap: 16px; height: 100%; }
.compare-figure { height: 300px; }
.compare-row { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
.compare-card { border-left: 4px solid #E3E0D7; padding-left: 22px; }
.compare-card.active { border-left-color: #E8733B; }
.edit-grid { display: grid; grid-template-columns: 620px 1fr; gap: 60px; height: 100%; align-items: center; }
.edit-text { display: flex; flex-direction: column; gap: 26px; }
.step-item { display: grid; grid-template-columns: 64px 1fr; gap: 18px; align-items: start; }
.step-number { font-size: 26px; font-weight: 700; color: #E8733B; letter-spacing: .08em; }
.edit-figure { height: 480px; }
.data-grid { display: grid; grid-template-columns: 1fr 520px; gap: 60px; height: 100%; align-items: center; }
.chart-container { height: 460px; }
.takeaway-box { border: 1px solid #E3E0D7; background: #FFFFFF; padding: 30px 34px; box-shadow: 0 4px 18px rgba(37,42,49,.06); }
.process-stack { display: flex; flex-direction: column; gap: 20px; height: 100%; }
.process-figure { height: 320px; }
.process-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; }
.process-step { border-top: 4px solid #E8733B; padding-top: 14px; }
.step-tag { font-size: 22px; font-weight: 700; color: #E8733B; letter-spacing: .1em; text-transform: uppercase; margin-bottom: 8px; }
/* P0 composition pilots */
.p01-stack { display: flex; flex-direction: column; gap: 14px; height: 100%; }
.p01-main { height: 270px; }
.p01-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
.p01-card { border-left: 4px solid #E3E0D7; padding-left: 20px; }
.p01-card.active { border-left-color: #E8733B; }
.p01-tag { font-size: 20px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #6B7280; }
.p01-card.active .p01-tag { color: #E8733B; }
.p01-card .deck-body { font-size: 26px; margin-top: 6px; }
.key-idea { display: flex; align-items: baseline; gap: 16px; border-left: 4px solid #E8733B; padding-left: 18px; font-size: 26px; color: #252A31; font-weight: 600; }
.key-tag { font-size: 19px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #E8733B; white-space: nowrap; }
.p02-grid { display: flex; gap: 50px; height: 100%; align-items: stretch; }
.p02-fig { flex: 0 0 auto; width: auto; height: 100%; }
.p02-fig img { height: 100%; width: auto; }
.p02-notes { flex: 1; list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; justify-content: center; gap: 30px; }
.p02-notes li { display: grid; grid-template-columns: 64px 1fr; gap: 18px; align-items: start; }
.note-num { font-size: 26px; font-weight: 700; color: #6B7280; letter-spacing: .08em; }
.p02-notes li.hot .note-num { color: #E8733B; }
.p02-notes li.hot .deck-body { color: #252A31; font-weight: 600; }
.p02-notes .deck-body { font-size: 28px; }
.p03-grid { display: grid; grid-template-columns: 1fr 360px 1fr; gap: 40px; height: 100%; align-items: center; }
.p03-col { display: flex; flex-direction: column; gap: 12px; }
.p03-label { font-size: 20px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #6B7280; }
.p03-fig { width: 100%; }
.p03-fig img { width: 100%; height: auto; }
.deck-caption-line { font-size: 24px; color: #2E3338; margin: 0; }
.p03-mid { display: flex; flex-direction: column; gap: 18px; align-items: center; text-align: center; }
.p03-relation { font-size: 30px; font-weight: 700; color: #252A31; margin: 0; }
.p03-confidence { font-size: 24px; color: #6B7280; margin: 0; }
.p07-stack { display: flex; flex-direction: column; gap: 14px; height: 100%; }
.p07-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; }
.p07-fig { height: 260px; }
.p07-head { display: flex; gap: 14px; align-items: baseline; margin-top: 10px; }
.p07-title { font-size: 26px; font-weight: 700; color: #252A31; }
.p07-col .deck-body { font-size: 24px; margin-top: 4px; }
.p07-scope { font-size: 22px; color: #6B7280; margin: 0; }
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


def compile_deck(paths: LessonPaths, font: str = "inter", out_dir: Path | None = None) -> dict:
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

    out_dir = Path(out_dir) if out_dir is not None else paths.build_root / "deck"
    out_dir.mkdir(parents=True, exist_ok=True)
    face_css = ""
    font_stack = SYSTEM_STACK
    if font != "default":
        rel, _family = FONT_SOURCES[font]
        src = lesson_dir.parent.parent / "references" / "fonts" / rel
        if not src.is_file():
            raise FileNotFoundError(f"local OFL font missing (no silent fallback): {src}")
        fonts_dir = out_dir / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, fonts_dir / src.name)
        ofl = src.parent / "OFL.txt"
        if ofl.is_file():
            shutil.copyfile(ofl, fonts_dir / "OFL.txt")
        face_css = (
            "@font-face{font-family:'DeckSans';src:url('fonts/" + src.name + "') format('truetype-variations');"
            "font-weight:100 900;font-style:normal;font-display:block;}"
        )
        font_stack = "'DeckSans', " + SYSTEM_STACK
    override_css = _OVERRIDE_CSS.replace("__FACE_CSS__", face_css).replace("__FONT_STACK__", font_stack)

    total = len(pages)
    sections = []
    manifest_pages = []
    citations = []
    assets_used: list[str] = []
    for idx, (seq, page) in enumerate(zip(plan.sequences, pages), start=1):
        archetype = "hero" if idx == 1 else choose_archetype(seq)
        if idx in P0_LAYOUTS:
            body = P0_LAYOUTS[idx](seq, page, slug, lesson_dir, pages)
        else:
            body = _RENDERERS[archetype](seq, page, slug, lesson_dir)
        for obj, _ in _figures(seq):
            if obj not in assets_used:
                assets_used.append(obj)
        headline = DISPLAY_TITLE.get(slug, page.heading) if idx == 1 else (page.heading or seq.title)
        kicker = HERO_KICKER if idx == 1 else f"{idx:02d} / {total:02d} · {_esc(seq.title)}"
        section = (
            f'<section class="slide--{archetype}">'
            f'<div class="kicker">{kicker}</div>'
            f'<h2 class="headline">{_esc(headline)}</h2>'
            f'<div class="main-visual">{body}</div>'
            f"{_footer(page, seq, archetype, idx, total, slug)}"
            "</section>"
        )
        sections.append(section)
        manifest_pages.append({"page": idx, "archetype": archetype, "has_source": bool(page.source)})
        citations.append({
            "page": idx,
            "display": _source_text(page, seq, archetype, idx, slug),
            "full": _full_source(page, seq, archetype, idx, slug),
            "slides_source": page.source,
            "page_correction": (slug, idx) in VERIFIED_BOOK_SOURCE,
        })

    out_file = out_dir / "index.html"
    title = f"{slug} · Deck"
    doc = _HEAD.format(title=_esc(title), override_css=override_css) + "\n".join(sections) + "\n" + _TAIL
    out_file.write_text(doc, encoding="utf-8")
    (out_dir / "citation-provenance.json").write_text(
        json.dumps({"lesson": slug, "citations": citations}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    production_sha = hashlib.sha256(production_file.read_bytes()).hexdigest()
    slides_sha = hashlib.sha256(slides_file.read_bytes()).hexdigest()
    manifest = {
        "lesson": slug,
        "pages": total,
        "font": font,
        "archetypes": manifest_pages,
        "assets_used": assets_used,
        "production_sha256": production_sha,
        "slides_sha256": slides_sha,
    }
    (out_dir / "deck-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest