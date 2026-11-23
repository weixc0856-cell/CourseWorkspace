"""E6: deck design binding — plain pages must never reach the sign-off gate.

Contract with the deck compiler (production.yaml -> build/<slug>/deck/index.html):

- one top-level <section> page per production sequence, in order;
- every page carries an EVDS archetype class: slide--hero / slide--editorial /
  slide--annotated / slide--comparison / slide--process / slide--data
  (版式系统 §3.1 canonical six);
- a sequence whose shots declare ``visual_type: book_figure_annotated`` must
  bind every ``assets/*.png`` object on its page via <img src|data-asset-src>;
- those book-figure pages must carry a non-empty ``.slide-footer .source``
  citation line (CSS contract: CourseSlides/css/mckinsey-orange.css:208).

Visual hard-defect checks (structure alone let garbage through once):

- instruction_leak: director instructions (spotlight / mask reveal / pin
  labels / sweep along / hold-the-callout, or any text chunk truncated with
  "…") must never appear as screen text;
- placeholder_mechanism: a page with no <img> whose main visual is an inline
  SVG containing a large rounded horizontal block (rx>0, width/height>2,
  width>=150, height>=40 viewBox units — the "rounded-rect car body" tell)
  is a placeholder, not a mechanism illustration.  Heuristic, strict side:
  thin chart bars (height<40) are exempt;
- data_binding: a slide--data page must carry real numbers in its body
  (a percentage, or >=3 standalone axis-tick numbers); footer folio and
  kicker numbers do not count.  "schematic — not measured" with no numbers
  fails.

A plain reveal.js shell fails.  Missing deck HTML or production contract is
``not_run`` (queued, never pass).  Shots-mode lessons are not applicable
(``not_run``); the sign-off gate only invokes this in deck mode.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ARCHETYPES = {
    "slide--hero", "slide--editorial", "slide--annotated",
    "slide--comparison", "slide--process", "slide--data",
}
_VOID = {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}
_INSTRUCTION = re.compile(
    r"spotlight|mask reveal|pin labels?|sweep along|hold the\b[^.]*callout",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent)")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pages: list[dict] = []
        self._depth = 0
        self._cur: dict | None = None
        self._stack: list[tuple[str, bool, bool, bool]] = []
        self._buf: list[str] = []
        self._svg = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "section":
            self._depth += 1
            if self._depth == 1:
                self._cur = {
                    "archetypes": sorted(c for c in cls if c in ARCHETYPES),
                    "imgs": [],
                    "source": "",
                    "chunks": [],
                    "body": [],
                    "svg_rects": [],
                }
                self._buf = []
                self._svg = 0
                self._skip = 0
        if self._cur is not None:
            if tag in ("script", "style"):
                self._skip += 1
            if tag == "svg":
                self._svg += 1
            if tag == "img":
                for key in ("src", "data-asset-src"):
                    if a.get(key):
                        self._cur["imgs"].append(a[key])
            if tag == "rect" and self._svg:
                try:
                    w = float(a.get("width") or 0)
                    h = float(a.get("height") or 0)
                    rx = float(a.get("rx") or 0)
                except ValueError:
                    w = h = rx = 0.0
                if rx > 0 and h > 0 and w / h > 2 and w >= 150 and h >= 40:
                    self._cur["svg_rects"].append((w, h, rx))
            in_footer = any(footer for _, footer, _, _ in self._stack)
            in_kicker = any(kicker for _, _, _, kicker in self._stack)
            is_footer = "slide-footer" in cls
            is_source = "source" in cls and in_footer
            is_kicker = "kicker" in cls
            if tag not in _VOID:
                self._stack.append((tag, is_footer, is_source, is_kicker))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and self._stack and self._stack[-1][0] == tag:
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "section":
            self._depth = max(0, self._depth - 1)
            if self._depth == 0 and self._cur is not None:
                self._cur["source"] = "".join(self._buf).strip()
                self.pages.append(self._cur)
                self._cur = None
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag == "svg":
            self._svg = max(0, self._svg - 1)
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self._cur is None or self._skip:
            return
        if any(source for _, _, source, _ in self._stack):
            self._buf.append(data)
        if data.strip():
            self._cur["chunks"].append(data.strip())
        if not any(footer or kicker for _, footer, _, kicker in self._stack):
            self._cur["body"].append(data)


def _book_assets(sequence: dict) -> list[str]:
    names: list[str] = []
    for shot in sequence.get("shots") or []:
        if shot.get("visual_type") != "book_figure_annotated":
            continue
        for obj in shot.get("objects") or []:
            if isinstance(obj, str) and obj.startswith("assets/") and obj.lower().endswith(".png"):
                names.append(obj.rsplit("/", 1)[-1])
    return names


def deck_design_problems(
    lesson_dir: Path, build_root: Path
) -> tuple[str, list[str], dict]:
    """Return (status, findings, stats) for the deck design binding contract."""
    import yaml

    lesson_dir = Path(lesson_dir)
    lesson_file = lesson_dir / "lesson.yaml"
    prod_file = lesson_dir / "authoring" / "production.yaml"
    deck_file = Path(build_root) / "deck" / "index.html"
    if not lesson_file.is_file():
        return "not_run", [f"lesson.yaml missing: {lesson_file}"], {}
    mode = ((yaml.safe_load(lesson_file.read_text(encoding="utf-8")) or {})
            .get("compose") or {}).get("mode")
    if mode != "deck":
        return "not_run", [f"deck design binding not applicable (compose.mode={mode})"], {"mode": mode}
    if not prod_file.is_file():
        return "not_run", [f"production contract missing: {prod_file}"], {}
    if not deck_file.is_file():
        return "not_run", [f"deck HTML missing: {deck_file}; compile production.yaml to EVDS deck first"], {}
    try:
        sequences = (yaml.safe_load(prod_file.read_text(encoding="utf-8")) or {}).get("sequences") or []
    except (OSError, yaml.YAMLError) as exc:
        return "fail", [f"production contract unreadable: {exc}"], {}

    parser = _PageParser()
    parser.feed(deck_file.read_text(encoding="utf-8"))
    pages = parser.pages
    stats = {"pages": len(pages), "sequences": len(sequences)}
    findings: list[str] = []
    if len(pages) != len(sequences):
        findings.append(f"page count {len(pages)} != sequence count {len(sequences)}")
    for index, seq in enumerate(sequences):
        if index >= len(pages):
            break
        page = pages[index]
        label = f"page {index + 1}"
        if not page["archetypes"]:
            findings.append(f"{label}: no EVDS archetype class (plain shell?)")
        assets = _book_assets(seq)
        if assets:
            bound = " ".join(page["imgs"])
            missing = [name for name in assets if name not in bound]
            if missing:
                findings.append(f"{label}: book figure not bound: {', '.join(missing)}")
            if not page["source"]:
                findings.append(f"{label}: book figure page lacks .slide-footer .source citation")
        for chunk in page["chunks"]:
            if _INSTRUCTION.search(chunk) or chunk.endswith("…"):
                findings.append(
                    f"{label}: director instruction leaked to screen: {chunk[:60]}"
                )
                break
        if not page["imgs"] and page["svg_rects"]:
            findings.append(
                f"{label}: placeholder mechanism (rounded-rect body block in SVG, "
                "no real illustration)"
            )
        if "slide--data" in page["archetypes"]:
            body = " ".join(page["body"])
            if not _PERCENT.search(body) and len(_NUMBER.findall(body)) < 3:
                findings.append(
                    f"{label}: data page carries no real numbers "
                    "(no percentage, fewer than 3 axis ticks)"
                )
    status = "fail" if findings else "pass"
    return status, findings, stats


def _deck_design(ctx: Any) -> tuple[str, Any, Any, str]:
    status, findings, stats = deck_design_problems(ctx.lesson_dir, ctx.build_root)
    actual = findings if findings else stats
    return status, actual, "deck design binding (archetypes + figures + citations)", str(ctx.lesson_dir)


DECK_DESIGN_RULES = {"deck_design_binding": _deck_design}