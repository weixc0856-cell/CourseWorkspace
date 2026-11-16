"""Check burned-subtitle bands against the picture bands.

frame-audit reads the Remotion composition, so it cannot see subtitles that
are burned in later by ffmpeg.  This check parses the ASS itself: every cue's
``\\pos`` anchor and line sizes give a vertical box, and that box must sit
inside ``subtitle_band`` from ``shared/design-tokens/episode-bands.yaml``.
The same file declares where the picture ends, so a subtitle band that would
overlap a footer or a conclusion line fails here instead of on screen.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

DEFAULT_BANDS = Path("shared/design-tokens/episode-bands.yaml")
LINE_HEIGHT = 1.2
TOLERANCE_PX = 2.0

_POS = re.compile(r"\\pos\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_AN = re.compile(r"\\an(\d)")
_FS = re.compile(r"\\fs(\d+(?:\.\d+)?)")
_BORD = re.compile(r"\\bord(\d+(?:\.\d+)?)")
_TAG = re.compile(r"\{[^}]*\}")


class BandError(RuntimeError):
    pass


def load_bands(path: Path) -> dict:
    if not path.is_file():
        raise BandError(f"band config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    subtitle = data.get("subtitle_band")
    picture = data.get("picture_bands") or {}
    if not (isinstance(subtitle, list) and len(subtitle) == 2):
        raise BandError(f"{path}: subtitle_band must be [top, bottom]")
    if not picture:
        raise BandError(f"{path}: picture_bands must not be empty")
    return data


def _styles(text: str) -> dict[str, dict]:
    styles: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.startswith("Style:"):
            continue
        fields = [item.strip() for item in line[len("Style:"):].split(",")]
        if len(fields) < 17:
            continue
        try:
            styles[fields[0]] = {"size": float(fields[2]), "outline": float(fields[16])}
        except ValueError:
            continue
    return styles


def _is_cjk(text: str) -> bool:
    return any("一" <= char <= "鿿" for char in text)


def parse_ass(text: str) -> list[dict]:
    styles = _styles(text)
    cues: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line[len("Dialogue:"):].split(",", 9)
        if len(fields) < 10:
            continue
        start, style, body = fields[1].strip(), fields[3].strip(), fields[9]
        style_info = styles.get(style, {"size": 34.0, "outline": 0.0})
        position = _POS.search(body)
        align_match = _AN.search(body)
        align = int(align_match.group(1)) if align_match else 2
        pieces = body.split("\\N")
        sizes = []
        outlines = []
        cjk_lines = []
        for piece in pieces:
            size_override = _FS.search(piece)
            outline_override = _BORD.search(piece)
            sizes.append(
                float(size_override.group(1)) if size_override else style_info["size"]
            )
            outlines.append(
                float(outline_override.group(1)) if outline_override else style_info["outline"]
            )
            cjk_lines.append(_is_cjk(_TAG.sub("", piece)))
        height = sum(size * LINE_HEIGHT for size in sizes)
        cues.append(
            {
                "start": start,
                "style": style,
                "x": float(position.group(1)) if position else None,
                "y": float(position.group(2)) if position else None,
                "align": align,
                "lines": len(pieces),
                "font_sizes": sizes,
                "outlines": outlines,
                "cjk_lines": cjk_lines,
                "height": height,
                "text": _TAG.sub("", body).replace("\\N", " ")[:80],
            }
        )
    return cues


def _box(cue: dict) -> tuple[float, float] | None:
    if cue["y"] is None:
        return None
    top = cue["y"] - cue["height"] if cue["align"] in (1, 2, 3) else cue["y"]
    return top, top + cue["height"]


def check_ass_band(ass_path: Path, bands_path: Path | None = None) -> dict:
    bands = load_bands(Path(bands_path or DEFAULT_BANDS))
    top, bottom = (float(value) for value in bands["subtitle_band"])
    picture = bands["picture_bands"]
    picture_max_bottom = max(float(value[-1]) for value in picture.values())
    if picture_max_bottom > top:
        return {
            "status": "FAIL",
            "detail": f"picture bands end at {picture_max_bottom:g} but subtitles start at {top:g}",
            "violations": [],
            "cues": 0,
            "subtitle_band": [top, bottom],
            "picture_max_bottom": picture_max_bottom,
        }
    cues = parse_ass(ass_path.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        return {
            "status": "FAIL",
            "detail": "no Dialogue lines in the ASS",
            "violations": [],
            "cues": 0,
            "subtitle_band": [top, bottom],
            "picture_max_bottom": picture_max_bottom,
        }
    violations = []
    readability = bands.get("readability") or {}
    min_size = float(readability.get("min_font_size") or 0)
    max_outline = float(readability.get("max_outline") or 0)
    max_outline_cjk = float(readability.get("max_outline_cjk") or max_outline)
    for index, cue in enumerate(cues, start=1):
        for line_index, (size, outline, cjk) in enumerate(
            zip(cue["font_sizes"], cue["outlines"], cue["cjk_lines"]), start=1
        ):
            if min_size and size < min_size:
                violations.append(
                    {
                        "index": index,
                        "start": cue["start"],
                        "detail": f"line {line_index} font {size:g} < {min_size:g}",
                    }
                )
            limit = max_outline_cjk if cjk else max_outline
            if limit and outline > limit + 1e-6:
                violations.append(
                    {
                        "index": index,
                        "start": cue["start"],
                        "detail": (
                            f"line {line_index} outline {outline:g} > {limit:g}"
                            + (" (CJK)" if cjk else "")
                        ),
                    }
                )
        box = _box(cue)
        if box is None:
            violations.append(
                {
                    "index": index,
                    "start": cue["start"],
                    "detail": "no \\pos; the band cannot be verified",
                }
            )
            continue
        cue_top, cue_bottom = box
        if cue_top < top - TOLERANCE_PX or cue_bottom > bottom + TOLERANCE_PX:
            violations.append(
                {
                    "index": index,
                    "start": cue["start"],
                    "top": round(cue_top, 1),
                    "bottom": round(cue_bottom, 1),
                    "detail": f"cue {cue_top:.0f}-{cue_bottom:.0f} outside band {top:g}-{bottom:g}",
                }
            )
    return {
        "status": "FAIL" if violations else "PASS",
        "detail": (
            f"{len(violations)} cue issue(s): band or readability"
            if violations
            else f"{len(cues)} cues inside {top:g}-{bottom:g}; picture ends at {picture_max_bottom:g}"
        ),
        "violations": violations[:20],
        "cues": len(cues),
        "subtitle_band": [top, bottom],
        "picture_max_bottom": picture_max_bottom,
    }


__all__ = ["BandError", "check_ass_band", "load_bands", "parse_ass"]
