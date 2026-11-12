"""AI-drafted course candidates and the human approval gate (R1-5A)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import yaml

from course_control.content.duration import resolve
from course_control.rendering.engine_router import VisualRequirement, route_engine
from course_control.content.paths import LessonPaths
from course_control.authoring.llm import AuthoringClient, AuthoringError
from course_control.authoring.models import (
    ApprovalEntry,
    ApprovalFile,
    Brief,
    ContentPage,
    NarrationScript,
    Outline,
    ScriptPage,
    SourceDigest,
)

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _prompt(name: str) -> str:
    path = PROMPTS / name
    if not path.is_file():
        raise AuthoringError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_dir(workspace: Path, lesson_dir: Path) -> Path:
    target = workspace.resolve() / "build" / lesson_dir.resolve().name / "authoring" / "candidates"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _brief_md(brief: Brief) -> str:
    lines = [f"# Course brief: {brief.lesson}", "", f"- audience: {brief.audience}", ""]
    lines += ["## Objectives", ""] + [f"- {item}" for item in brief.objectives] + [""]
    if brief.prerequisites:
        lines += ["## Prerequisites", ""] + [f"- {item}" for item in brief.prerequisites] + [""]
    lines += ["## Duration", "", f"```json\n{json.dumps(brief.duration, ensure_ascii=False, indent=2)}\n```", ""]
    if brief.scope_in:
        lines += ["## In scope", ""] + [f"- {item}" for item in brief.scope_in] + [""]
    if brief.scope_out:
        lines += ["## Out of scope", ""] + [f"- {item}" for item in brief.scope_out] + [""]
    if brief.assumptions:
        lines += ["## Assumptions", ""] + [f"- {item}" for item in brief.assumptions] + [""]
    return "\n".join(lines).rstrip() + "\n"


def _outline_md(outline: Outline) -> str:
    lines = [f"# Course outline: {outline.lesson}", ""]
    for chapter in outline.chapters:
        lines += [f"## {chapter.id} · {chapter.title}", ""]
        lines.append("| slide | title | seconds | visual | source refs |")
        lines.append("| --- | --- | --- | --- | --- |")
        for page in chapter.pages:
            refs = ", ".join(page.source_refs) or "original framing"
            lines.append(
                f"| {page.slide} | {page.title} | {page.target_seconds:g} | "
                f"{page.visual_kind} | {refs} |"
            )
        lines.append("")
    lines += ["## Totals", "", f"```json\n{json.dumps(outline.totals, ensure_ascii=False, indent=2)}\n```", ""]
    return "\n".join(lines).rstrip() + "\n"


def _script_md(script: NarrationScript) -> str:
    lines = [f"# Narration script: {script.lesson}", "", f"- language: {script.language}", ""]
    for page in script.pages:
        lines += [f"## Slide {page.slide} · target {page.target_seconds:g}s", ""]
        for segment in page.segments:
            style = f" **{segment.style}**" if segment.style else ""
            lines.append(f"- `{segment.id}`{style} — {segment.text}")
            if segment.pause_after_ms:
                lines.append(f"  - pause after: {segment.pause_after_ms} ms")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _digest_text(digest: SourceDigest, refs: list[str] | None = None, max_chars: int = 24000) -> str:
    sections = digest.sections
    if refs:
        wanted = set(refs)
        sections = [section for section in sections if section.ref in wanted]
    lines: list[str] = []
    used = 0
    for section in sections:
        block = (
            f"## {section.ref} · {section.heading}\n"
            f"source: {section.source_id}; lines: {section.line_start}-{section.line_end}\n"
            f"{section.excerpt}\n"
        )
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    if not lines:
        raise AuthoringError("no digest sections matched the requested refs")
    return "\n".join(lines)


def _lesson_context(paths: LessonPaths) -> str:
    lesson = paths.lesson
    policy = resolve(lesson)
    duration = policy.as_dict() if policy else {"profile": "none"}
    return (
        f"lesson_id: {lesson.lesson_id}\n"
        f"title_en: {lesson.title_en}\n"
        f"title_zh: {lesson.title_zh}\n"
        f"status: {lesson.status}\n"
        f"engines: {', '.join(lesson.engines)}\n"
        f"duration: {json.dumps(duration, ensure_ascii=False)}\n"
        f"resolution: {lesson.outputs.resolution[0]}x{lesson.outputs.resolution[1]} @ {lesson.outputs.fps}fps\n"
    )


def generate_brief(
    client: AuthoringClient,
    workspace: Path,
    lesson_dir: Path,
    digest: SourceDigest,
) -> Brief:
    paths = LessonPaths.load(workspace, lesson_dir)
    messages = [
        {"role": "system", "content": _prompt("course_brief.md")},
        {
            "role": "user",
            "content": (
                "Lesson metadata:\n"
                + _lesson_context(paths)
                + "\nSource digest:\n"
                + _digest_text(digest)
            ),
        },
    ]
    brief = client.chat_json(messages, Brief, task_type="authoring.brief")
    brief = brief.model_copy(
        update={
            "generator": {
                "provider": client.route.provider if client.route else "local",
                "model": client.route.model if client.route else "",
                "task_id": None,
            }
        }
    )
    target = candidate_dir(workspace, lesson_dir)
    _write_json(target / "brief.json", brief)
    _write_md(target / "brief.md", _brief_md(brief))
    return brief


def generate_outline(
    client: AuthoringClient,
    workspace: Path,
    lesson_dir: Path,
    digest: SourceDigest,
    brief: Brief,
) -> Outline:
    messages = [
        {"role": "system", "content": _prompt("course_outline.md")},
        {
            "role": "user",
            "content": (
                "Brief:\n"
                + json.dumps(brief.model_dump(mode="json"), ensure_ascii=False, indent=2)
                + "\n\nSource digest:\n"
                + _digest_text(digest)
            ),
        },
    ]
    outline = client.chat_json(messages, Outline, task_type="authoring.outline")
    pages = outline.pages
    if [page.slide for page in pages] != list(range(1, len(pages) + 1)):
        raise AuthoringError("outline pages must be numbered 1..N in order")
    total = sum(page.target_seconds for page in pages)
    target_seconds = float(
        (outline.totals or {}).get("target_seconds")
        or brief.duration.get("target_seconds")
        or 0
    )
    min_seconds = float(brief.duration.get("min_seconds") or 0)
    max_seconds = float(brief.duration.get("max_seconds") or 10**9)
    if total < min_seconds or total > max_seconds:
        correction = (
            f"Your page budgets sum to {total:.1f}s, but the allowed course window is "
            f"{min_seconds:.1f}-{max_seconds:.1f}s (target {target_seconds:.1f}s). "
            "Keep the same chapters and page topics, but adjust target_seconds so the "
            "total is inside the window and close to the target. Return the corrected "
            "JSON only."
        )
        outline = client.chat_json(
            [
                *messages,
                {
                    "role": "assistant",
                    "content": json.dumps(outline.model_dump(mode="json"), ensure_ascii=False),
                },
                {"role": "user", "content": correction},
            ],
            Outline,
            task_type="authoring.outline.repair",
        )
        total = sum(page.target_seconds for page in outline.pages)
        if total < min_seconds or total > max_seconds:
            raise AuthoringError(
                f"outline page budgets sum to {total:.1f}s, outside "
                f"{min_seconds:.1f}-{max_seconds:.1f}s"
            )
    target = candidate_dir(workspace, lesson_dir)
    _write_json(target / "outline.json", outline)
    _write_md(target / "outline.md", _outline_md(outline))
    return outline


def generate_script(
    client: AuthoringClient,
    workspace: Path,
    lesson_dir: Path,
    digest: SourceDigest,
    outline: Outline,
) -> NarrationScript:
    pages: list[ScriptPage] = []
    for page in outline.pages:
        messages = [
            {"role": "system", "content": _prompt("course_script.md")},
            {
                "role": "user",
                "content": (
                    f"Lesson: {lesson_dir.name}\n"
                    f"Slide: {page.slide}\n"
                    f"Title: {page.title}\n"
                    f"Claim: {page.claim}\n"
                    f"Target seconds: {page.target_seconds}\n"
                    f"Source refs: {', '.join(page.source_refs) or 'original framing'}\n\n"
                    "Source excerpts:\n"
                    + _digest_text(digest, page.source_refs or None, max_chars=16000)
                ),
            },
        ]
        page_script = client.chat_json(
            messages,
            ScriptPage,
            task_type=f"authoring.script.slide-{page.slide:03d}",
        )
        if page_script.slide != page.slide:
            raise AuthoringError(
                f"script page {page_script.slide} does not match outline slide {page.slide}"
            )
        pages.append(page_script)
        _write_json(
            candidate_dir(workspace, lesson_dir) / f"script-{page.slide:03d}.json",
            page_script,
        )
    script = NarrationScript(
        lesson=lesson_dir.name,
        language="en",
        voice={"ref_audio": "config:tts.voice_ref_en|tts.voice_ref", "style_enabled": True},
        policy={"min_segment_seconds": 2.0, "max_segment_seconds": 35.0, "page_pause_ms": 600},
        pages=pages,
    )
    target = candidate_dir(workspace, lesson_dir)
    _write_json(target / "narration.script.json", script)
    _write_md(target / "narration.script.md", _script_md(script))
    return script


def _scene_path(lesson: str, engine: str, name: str) -> str:
    if engine == "manim":
        class_name = "".join(part.capitalize() for part in name.replace("-", "_").split("_")) + "Scene"
        return f"{lesson}/{name}.py::{class_name}"
    if engine == "blender":
        return f"scenes/{lesson}/{name}.blend"
    return f"src/scenes/{lesson}/{name}.tsx"


def generate_content(
    client: AuthoringClient,
    workspace: Path,
    lesson_dir: Path,
    digest: SourceDigest,
    outline: Outline,
    script: NarrationScript,
) -> dict[str, str]:
    slides: list[str] = []
    notes: list[str] = []
    shots: list[dict] = []
    script_by_slide = {page.slide: page for page in script.pages}

    for page in outline.pages:
        script_page = script_by_slide.get(page.slide)
        if script_page is None:
            raise AuthoringError(f"missing script for slide {page.slide}")
        messages = [
            {"role": "system", "content": _prompt("course_content.md")},
            {
                "role": "user",
                "content": (
                    f"Lesson: {lesson_dir.name}\n"
                    f"Slide: {page.slide}\n"
                    f"Title: {page.title}\n"
                    f"Claim: {page.claim}\n"
                    f"Visual: {page.visual} ({page.visual_kind})\n"
                    f"Narration (already written, do not duplicate):\n"
                    + " ".join(segment.text for segment in script_page.segments)
                    + "\n\nSource excerpts:\n"
                    + _digest_text(digest, page.source_refs or None, max_chars=12000)
                ),
            },
        ]
        content = client.chat_json(
            messages,
            ContentPage,
            task_type=f"authoring.content.slide-{page.slide:03d}",
        )
        if content.slide != page.slide:
            content = client.chat_json(
                [
                    *messages,
                    {
                        "role": "assistant",
                        "content": json.dumps(content.model_dump(mode="json"), ensure_ascii=False),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"You returned slide {content.slide}, but this request is for "
                            f"slide {page.slide} ({page.title}). Regenerate the slide and "
                            "notes content for this slide only. Return JSON only."
                        ),
                    },
                ],
                ContentPage,
                task_type=f"authoring.content.slide-{page.slide:03d}.repair",
            )
        if content.slide != page.slide:
            raise AuthoringError(
                f"content page {content.slide} does not match outline slide {page.slide}"
            )
        block = f"## {content.title}\n\n{content.slide_markdown.strip()}"
        # A literal --- would become a page separator in slides.md.
        block = re.sub(r"(?m)^\s*---\s*$", "<hr />", block)
        if content.zh_sub.strip():
            block += f"\n\n<div class=\"zh-sub\"><p>{content.zh_sub.strip()}</p></div>"
        slides.append(block)
        narration_text = " ".join(segment.text for segment in script_page.segments)
        notes.append(
            f"### Slide {page.slide}: {content.title}\n\n"
            f"- **时长预算**：{page.target_seconds:g} 秒\n"
            f"- **动画切入**：{page.animation or '无'}\n"
            f"- **技术核查**：{content.technical_check or '无'}\n\n"
            f"#### 逐字口播\n\n{narration_text}"
        )
        if page.animation:
            route = route_engine(
                VisualRequirement(
                    kind=page.visual_kind,
                    needs_3d=page.needs_3d,
                    duration_s=page.target_seconds,
                )
            )
            shot = {
                "id": f"shot_{page.slide:03d}",
                "slide": page.slide,
                "engine": route.engine,
                "scene": _scene_path(lesson_dir.name, route.engine, page.animation),
                "cue_seconds": min(30.0, max(0.0, page.target_seconds / 3)),
                "expected_duration_s": None,
                "engine_profile": route.profile,
            }
            if route.engine == "blender":
                shot["blend_task"] = f"tasks/{lesson_dir.name}/{page.animation}.json"
            shots.append(shot)

    target = candidate_dir(workspace, lesson_dir)
    slides_md = "\n\n---\n\n".join(slides) + "\n"
    notes_md = "\n\n---\n\n".join(notes) + "\n"
    storyboard = {
        "schema_version": 1,
        "lesson": lesson_dir.name,
        "shots": shots,
    }
    (target / "slides.md").write_text(slides_md, encoding="utf-8")
    (target / "lecture_notes.md").write_text(notes_md, encoding="utf-8")
    (target / "storyboard.yaml").write_text(
        yaml.safe_dump(storyboard, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {
        "slides": str(target / "slides.md"),
        "notes": str(target / "lecture_notes.md"),
        "storyboard": str(target / "storyboard.yaml"),
    }


# -- approval gate ---------------------------------------------------------


def approval_path(lesson_dir: Path) -> Path:
    return lesson_dir.resolve() / "authoring" / "approval.json"


def load_approval(lesson_dir: Path) -> ApprovalFile:
    path = approval_path(lesson_dir)
    if not path.is_file():
        return ApprovalFile(lesson=lesson_dir.resolve().name)
    return ApprovalFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_approval(lesson_dir: Path, approval: ApprovalFile) -> Path:
    path = approval_path(lesson_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(approval.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def approve(lesson_dir: Path, kind: str, relative_path: str) -> ApprovalEntry:
    target = lesson_dir.resolve() / relative_path
    if not target.is_file():
        raise AuthoringError(f"cannot approve missing file: {target}")
    approval = load_approval(lesson_dir)
    entry = ApprovalEntry(
        kind=kind,
        path=relative_path,
        sha256=_sha(target),
        approved_by="human",
        approved_at=_now(),
    )
    approval.approvals.append(entry)
    save_approval(lesson_dir, approval)
    return entry


def assert_approved(lesson_dir: Path, relative_path: str) -> None:
    target = lesson_dir.resolve() / relative_path
    if not target.is_file():
        raise AuthoringError(f"approved file is missing: {target}")
    approval = load_approval(lesson_dir)
    entry = approval.find(relative_path)
    if entry is None:
        raise AuthoringError(f"file has no approval entry: {relative_path}")
    if entry.sha256 != _sha(target):
        raise AuthoringError(f"file changed after approval: {relative_path}")


CONTENT_TARGETS = {
    "slides": "slides.md",
    "notes": "lecture_notes.md",
    "storyboard": "storyboard.yaml",
}


def accept_artifact(workspace: Path, lesson_dir: Path, kind: str) -> list[str]:
    """Copy a candidate artifact into lessons/<slug>/authoring and approve it."""
    source = candidate_dir(workspace, lesson_dir)
    lesson_dir = lesson_dir.resolve()
    mapping = {
        "brief": [
            ("brief.json", "authoring/brief.json"),
            ("brief.md", "authoring/brief.md"),
        ],
        "outline": [
            ("outline.json", "authoring/outline.json"),
            ("outline.md", "authoring/outline.md"),
        ],
        "script": [
            ("narration.script.json", "authoring/narration.script.json"),
            ("narration.script.md", "authoring/narration.script.md"),
        ],
        "digest": [
            ("source-digest.json", "authoring/source-digest.json"),
            ("source-digest.md", "authoring/source-digest.md"),
        ],
    }
    if kind not in mapping:
        raise AuthoringError(f"unknown approval kind: {kind}")
    written: list[str] = []
    primary = mapping[kind][0][1]
    for candidate_name, relative in mapping[kind]:
        src = source / candidate_name
        if not src.is_file():
            # Digest was generated in the lesson directory, not in candidates.
            src = lesson_dir / relative
        if not src.is_file():
            raise AuthoringError(f"candidate missing: {candidate_name}")
        dst = lesson_dir / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(relative)
    approve(lesson_dir, kind, primary)
    return written


def accept_content(workspace: Path, lesson_dir: Path) -> list[str]:
    """Promote approved candidate content into lessons/<slug>/."""
    source = candidate_dir(workspace, lesson_dir)
    mapping = {
        "slides": (source / "slides.md", lesson_dir.resolve() / "slides.md"),
        "notes": (source / "lecture_notes.md", lesson_dir.resolve() / "lecture_notes.md"),
        "storyboard": (source / "storyboard.yaml", lesson_dir.resolve() / "storyboard.yaml"),
    }
    written: list[str] = []
    for _, (src, dst) in mapping.items():
        if not src.is_file():
            raise AuthoringError(f"candidate missing: {src}")
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(dst.relative_to(lesson_dir.resolve()).as_posix())
    for relative in written:
        approve(lesson_dir, "content", relative)
    return written
