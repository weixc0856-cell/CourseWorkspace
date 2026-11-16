"""Audit a lesson's per-segment binding before anything is rendered.

Three failures made the first twelve-minute cut unusable, and none of them was
visible to the existing gates:

* every chart card pointed at the same default figure, so one curve illustrated
  eight different topics;
* every card carried the opening act's eyebrow and headline, so a chapter about
  the Golf was titled "The Golf case" over a Mercedes photograph;
* the narration said "the book" twelve times, which reads as a book report
  rather than a lecture.

This script reports all three from the authoring data. It is a report, not a
gate: the counts are meant to be read before the storyboard is rewritten.

Usage:
    uv run --project CourseControl python scripts/check_segment_assets.py \
        --lesson-dir <content_root>/lessons/<slug>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

BANNED_PHRASES = [
    r"\bthe book\b",
    r"\baccording to the book\b",
    r"\bthe book shows\b",
    r"\bthe book says\b",
]

# Props a component needs before it can honestly render a segment. Mirrors
# REQUIRED in RemotionStudio/src/episode/Episode.tsx.
REQUIRED = {
    "PhotoInsert": ["image", "eyebrow", "headline"],
    "ChartOverlay": ["image", "eyebrow", "title", "source"],
    "MechanismDiagram": ["eyebrow", "title"],
    "CarFlowScene": ["eyebrow", "headline"],
    "FormulaBlock": ["tex", "title"],
    "PointsCard": ["eyebrow", "title", "points"],
}

# CLAUDE.md §2.12: evidence stays evidence. A mechanism or flow figure must
# sit on an original book figure or declare why it is built from scratch.
FIGURE_COMPONENTS = {"MechanismDiagram", "CarFlowScene"}
CUSTOM_BUILD_REASONS = {"formula_animation", "summary_card", "no_book_figure"}


def load_beats(lesson_dir: Path) -> list[dict]:
    path = lesson_dir / "authoring" / "beat-segments.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("beats") or []


def load_script(lesson_dir: Path) -> list[dict]:
    path = lesson_dir / "authoring" / "narration.script.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [seg for page in data.get("pages") or [] for seg in page.get("segments") or []]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lesson-dir", required=True)
    args = parser.parse_args()
    lesson_dir = Path(args.lesson_dir)
    beats = load_beats(lesson_dir)

    missing: list[str] = []
    images: dict[str, list[str]] = defaultdict(list)
    eyebrows: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, list[str]] = defaultdict(list)

    for beat in beats:
        for index, instance in enumerate(beat.get("instances") or []):
            name = instance.get("component")
            props = instance.get("props") or {}
            where = f'{beat.get("id")}#{index} {name}'
            for key in REQUIRED.get(name, []):
                if props.get(key) in (None, ""):
                    missing.append(f"{where}.{key}")
            if name in FIGURE_COMPONENTS:
                base = props.get("base_image")
                reason = props.get("custom_build_reason")
                has_base = isinstance(base, str) and base.startswith("staging/ref_figs/")
                if not has_base and reason not in CUSTOM_BUILD_REASONS:
                    missing.append(
                        f"{where}: {name} requires base_image from ref_figs "
                        "(CLAUDE.md §2.12) or a custom_build_reason"
                    )
            if props.get("image"):
                images[str(props["image"])].append(where)
            if props.get("eyebrow"):
                eyebrows[str(props["eyebrow"])].append(where)
            if props.get("title"):
                titles[str(props["title"])].append(where)

    shared_images = {img: uses for img, uses in images.items() if len(uses) > 1}
    repeated_eyebrows = {e: uses for e, uses in eyebrows.items() if len(uses) > 1}
    repeated_titles = {t: uses for t, uses in titles.items() if len(uses) > 1}

    segments = load_script(lesson_dir)
    banned_hits = []
    for segment in segments:
        text = segment.get("text") or ""
        for pattern in BANNED_PHRASES:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                banned_hits.append((segment.get("id"), match.group(0)))

    total_instances = sum(len(beat.get("instances") or []) for beat in beats)
    print(f"instances: {total_instances} across {len(beats)} beats")
    print()

    print(f"[missing required props] {len(missing)}")
    for item in missing:
        print(f"  {item}")
    print()

    print(f"[image reused] {len(shared_images)}")
    for img, uses in sorted(shared_images.items(), key=lambda kv: -len(kv[1])):
        print(f"  {img}: {len(uses)} uses -> {', '.join(uses)}")
    print()

    print(f"[eyebrow repeated] {len(repeated_eyebrows)}")
    for text, uses in sorted(repeated_eyebrows.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  {text!r}: {len(uses)} times")
    print()

    print(f"[title repeated] {len(repeated_titles)}")
    for text, uses in sorted(repeated_titles.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  {text!r}: {len(uses)} times")
    print()

    counter = Counter(hit[1].lower() for hit in banned_hits)
    print(f"[banned phrases] {len(banned_hits)}")
    for phrase, count in counter.most_common():
        print(f"  {phrase!r}: {count}")
    for segment_id, phrase in banned_hits:
        print(f"  {segment_id}: {phrase!r}")

    problems = len(missing) + len(shared_images) + len(banned_hits)
    print()
    print("verdict:", "needs binding work" if problems else "clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
