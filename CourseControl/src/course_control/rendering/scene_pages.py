"""Render the per-page ScenePage clips that ``compose.mode=scene`` requires.

``collect`` reads ``build/<slug>/scenes/manifest.json`` and refuses to run
without it, but nothing produced that manifest — the scene mode worked only on
lessons where someone had rendered the pages by hand.  This module closes that
gap: one full-screen clip per page, timed by measured narration, plus the
manifest.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from course_control.authoring.models import NarrationScript, Outline
from course_control.content.contracts import Status
from course_control.content.paths import LessonPaths
from course_control.platform.utils import run_command, which_command
from course_control.rendering.adapters.base import StageOutcome
from course_control.rendering.theme import load_theme

MANIFEST = "scenes/manifest.json"

MAX_BEAT_CHARS = 110


def split_beats(text: str) -> list[str]:
    """Sentence-sized beats: ScenePage shows one line group at 50-70 px."""
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if part.strip()]
    beats: list[str] = []
    for part in parts:
        if len(part) <= MAX_BEAT_CHARS:
            beats.append(part)
            continue
        # Long sentences are split at clause boundaries, never mid-word.
        clause = ""
        for fragment in re.split(r"(?<=[,;:])\s+", part):
            candidate = f"{clause} {fragment}".strip()
            if clause and len(candidate) > MAX_BEAT_CHARS:
                beats.append(clause)
                clause = fragment
            else:
                clause = candidate
        if clause:
            beats.append(clause)
    return beats or [text.strip()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _page_props(
    paths: LessonPaths,
    *,
    accent: str,
) -> list[dict]:
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"narration metadata not found: {meta_path}")
    meta = _read_json(meta_path)

    outline_name = paths.lesson.authoring.outline if paths.lesson.authoring else None
    if not outline_name:
        raise FileNotFoundError("lesson.authoring.outline is required for scene pages")
    outline = Outline.model_validate_json(
        (paths.lesson_dir / outline_name).read_text(encoding="utf-8")
    )

    script_name = paths.lesson.authoring.script if paths.lesson.authoring else None
    script = (
        NarrationScript.model_validate_json(
            (paths.lesson_dir / script_name).read_text(encoding="utf-8")
        )
        if script_name
        else None
    )

    section_of = {
        page.slide: chapter.title for chapter in outline.chapters for page in chapter.pages
    }
    title_of = {page.slide: page.title for chapter in outline.chapters for page in chapter.pages}

    texts: dict[int, list[dict]] = {}
    if script is not None:
        for page in script.pages:
            texts[page.slide] = [
                {"text": segment.text} for segment in page.segments
            ]

    segment_times = {
        str(segment.get("segment_id")): (
            float(segment.get("start_s") or 0.0),
            float(segment.get("end_s") or segment.get("start_s") or 0.0),
        )
        for segment in meta.get("segments") or []
    }
    segment_ids: dict[int, list[str]] = {}
    if script is not None:
        for page in script.pages:
            segment_ids[page.slide] = [segment.id for segment in page.segments]

    pages = sorted(meta.get("pages") or [], key=lambda item: int(item["slide"]))
    total = len(pages)
    props: list[dict] = []
    for item in pages:
        slide = int(item["slide"])
        start = float(item.get("start_s") or 0.0)
        duration = float(item.get("measured_s") or item.get("planned_s") or 0.0)
        beats = []
        for index, entry in enumerate(texts.get(slide, [])):
            ids = segment_ids.get(slide, [])
            if index >= len(ids):
                continue
            seg_start, seg_end = segment_times.get(ids[index], (start, start + 1.0))
            window = max(0.5, seg_end - seg_start)
            pieces = split_beats(entry["text"])
            total_chars = sum(len(piece) for piece in pieces) or 1
            cursor = seg_start
            for piece_index, piece in enumerate(pieces):
                beats.append(
                    {
                        "at_s": max(0.0, round(cursor - start, 3)),
                        "text": piece,
                        "accent": index == 0 and piece_index == 0,
                    }
                )
                cursor += window * len(piece) / total_chars
        props.append(
            {
                "page": slide,
                "total_pages": total,
                "section": section_of.get(slide, ""),
                "title": title_of.get(slide, f"Page {slide}"),
                "beats": beats,
                "duration_s": round(duration, 3),
                "accent": accent,
            }
        )
    return props


def _manifest(paths: LessonPaths, props: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "base_file": None,
        "pages": [
            {
                "file": f"scenes/pages/page-{item['page']:03d}.mp4",
                "slide": item["page"],
                "duration_s": item["duration_s"],
            }
            for item in props
        ],
    }


def run(paths: LessonPaths, *, force: bool = False) -> StageOutcome:
    """Render every page, or reuse an existing manifest."""
    started = time.monotonic()
    scenes = paths.build_root / "scenes"
    manifest_path = paths.build_root / MANIFEST

    if manifest_path.is_file() and not force:
        manifest = _read_json(manifest_path)
        missing = [
            page["file"]
            for page in manifest.get("pages") or []
            if not (paths.build_root / page["file"]).is_file()
        ]
        if not missing:
            # A complete manifest is this stage's output, not a skipped stage:
            # reporting SKIPPED would make a good build verdict "incomplete".
            return StageOutcome(
                "render:scenes",
                Status.PASS,
                outputs=[manifest_path],
                warnings=["reused the existing scene manifest; every page file is present"],
                reason="manifest_present",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    try:
        theme = load_theme(paths.workspace)
        accent = theme.get("colors", {}).get("accent", "#E8733B")
        props = _page_props(paths, accent=accent)
    except (FileNotFoundError, ValueError) as exc:
        return StageOutcome(
            "render:scenes",
            Status.FAIL,
            errors=[str(exc)],
            reason="scene_pages_unavailable",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if not props:
        return StageOutcome(
            "render:scenes",
            Status.FAIL,
            errors=["narration metadata has no pages"],
            reason="scene_pages_unavailable",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    pages_dir = scenes / "pages"
    props_dir = scenes / "props"
    pages_dir.mkdir(parents=True, exist_ok=True)
    props_dir.mkdir(parents=True, exist_ok=True)
    remotion_root = paths.workspace / "RemotionStudio"
    log_dir = paths.build_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    for item in props:
        slide = item["page"]
        props_file = props_dir / f"page-{slide:03d}.json"
        props_file.write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        target = pages_dir / f"page-{slide:03d}.mp4"
        render = run_command(
            [
                *which_command("npx"),
                "remotion",
                "render",
                "src/index.ts",
                "ScenePage",
                str(target),
                f"--props={props_file}",
                "--timeout=120000",
            ],
            remotion_root,
            timeout=900,
            log_path=log_dir / f"scene-page-{slide:03d}.log",
        )
        if render.exit_code != 0 or not target.is_file():
            return StageOutcome(
                "render:scenes",
                Status.FAIL,
                errors=[
                    f"page {slide}: remotion exited {render.exit_code}",
                    render.stderr[-1500:],
                ],
                reason="scene_page_failed",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    manifest = _manifest(paths, props)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return StageOutcome(
        "render:scenes",
        Status.PASS,
        outputs=[manifest_path, pages_dir],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
