"""AI-drafted course candidates and the human approval gate (R1-5A)."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from course_control.content.duration import resolve
from course_control.rendering.engine_router import VisualRequirement, route_engine
from course_control.content.paths import LessonPaths
from course_control.platform.workspace_layout import build_root_for
from course_control.quality.evidence import is_named_approver
from course_control.production.course_chain import (
    assert_lesson_course_chain,
    default_chain_config,
)
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


def candidate_dir(
    workspace: Path, lesson_dir: Path, *, create: bool = True
) -> Path:
    """Candidate drafts live in the content root, never in the program workspace.

    Resolving ``workspace / "build"`` wrote authoring candidates into the
    repository whenever the command ran from the repo root, which the
    separation check then reported as course content leaking into the code.
    """
    target = build_root_for(workspace, lesson_dir.resolve().name) / "authoring" / "candidates"
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


CANDIDATE_RECORD = "candidates.json"


def _candidate_record(directory: Path) -> dict:
    path = directory / CANDIDATE_RECORD
    if not path.is_file():
        return {"schema_version": 1, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": 1, "files": {}}
    if not isinstance(data, dict):
        return {"schema_version": 1, "files": {}}
    if not isinstance(data.get("files"), dict):
        data["files"] = {}
    return data


def _record_candidates(
    workspace: Path, lesson_dir: Path, entries: dict[str, str]
) -> None:
    """Record what each candidate was generated from.

    A candidate is a draft against a target that existed at generation time.
    Without this record ``author-accept`` cannot tell a fresh draft from one
    generated against a file that has since been edited by hand, so the record
    is what makes "refuse a stale candidate" possible at all.
    """
    directory = candidate_dir(workspace, lesson_dir)
    data = _candidate_record(directory)
    files = data["files"]
    now = _now()
    for name, relative in entries.items():
        candidate = directory / name
        if not candidate.is_file():
            continue
        target = lesson_dir.resolve() / relative
        files[name] = {
            "candidate": name,
            "target": relative,
            "candidate_sha256": _sha(candidate),
            "target_sha256": _sha(target) if target.is_file() else None,
            "generated_at": now,
        }
    data["schema_version"] = 1
    data["lesson"] = lesson_dir.resolve().name
    _write_json(directory / CANDIDATE_RECORD, data)


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


def _lesson_context(lesson: LessonConfig) -> str:
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
    lesson_yaml = lesson_dir / "lesson.yaml"
    if not lesson_yaml.is_file():
        raise AuthoringError(f"lesson.yaml not found: {lesson_yaml}")
    from course_control.content.contracts import LessonConfig

    lesson = LessonConfig.model_validate(
        yaml.safe_load(lesson_yaml.read_text(encoding="utf-8"))
    )
    messages = [
        {"role": "system", "content": _prompt("course_brief.md")},
        {
            "role": "user",
            "content": (
                "Lesson metadata:\n"
                + _lesson_context(lesson)
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
    _record_candidates(
        workspace,
        lesson_dir,
        {"brief.json": "authoring/brief.json", "brief.md": "authoring/brief.md"},
    )
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
    _record_candidates(
        workspace,
        lesson_dir,
        {"outline.json": "authoring/outline.json", "outline.md": "authoring/outline.md"},
    )
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
    _record_candidates(
        workspace,
        lesson_dir,
        {
            "narration.script.json": "authoring/narration.script.json",
            "narration.script.md": "authoring/narration.script.md",
        },
    )
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
    _record_candidates(
        workspace,
        lesson_dir,
        {
            "slides.md": "slides.md",
            "lecture_notes.md": "lecture_notes.md",
            "storyboard.yaml": "storyboard.yaml",
        },
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


def approve(
    lesson_dir: Path, kind: str, relative_path: str, approved_by: str
) -> ApprovalEntry:
    if not is_named_approver(approved_by):
        raise AuthoringError(
            f"approval must name a person, not {approved_by!r}"
        )
    target = lesson_dir.resolve() / relative_path
    if not target.is_file():
        raise AuthoringError(f"cannot approve missing file: {target}")
    approval = load_approval(lesson_dir)
    entry = ApprovalEntry(
        kind=kind,
        path=relative_path,
        sha256=_sha(target),
        approved_by=approved_by.strip(),
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
    if not is_named_approver(entry.approved_by):
        raise AuthoringError(
            f"file was approved by {entry.approved_by!r}, not a named person; "
            "approve it again with --by"
        )
    if entry.sha256 != _sha(target):
        raise AuthoringError(f"file changed after approval: {relative_path}")


SIGNOFF_KIND = "storyboard-page"
SIGNOFF_FILE = "authoring/storyboard-review.json"


def sign_storyboard_page(
    workspace: Path, lesson_dir: Path, approved_by: str
) -> list[str]:
    """Record the owner's sign-off on the static storyboard page.

    The reviewed page is copied into the lesson, so later build cleanup or a
    replaced slide capture cannot change what was signed.  The review file pins
    the effective storyboard, the page, the slide source and the page's own
    hash; ``approval.json`` pins the review file itself.
    """
    if not is_named_approver(approved_by):
        raise AuthoringError(
            f"storyboard sign-off must name a person, not {approved_by!r}"
        )
    lesson_dir = lesson_dir.resolve()
    from course_control.content.paths import LessonPaths

    paths = LessonPaths.load(Path(workspace).resolve(), lesson_dir)
    chain = assert_lesson_course_chain(
        Path(workspace).resolve(),
        lesson_dir,
        config_path=default_chain_config(),
    )
    chain_fingerprint = chain.fingerprint if chain is not None else None
    source = paths.storyboard_source
    if source is None:
        raise AuthoringError("lesson has no storyboard or production source to sign")
    source = Path(source).resolve()
    if not source.is_file():
        raise AuthoringError(f"storyboard source is missing: {source}")

    page_dir = build_root_for(workspace, lesson_dir.name) / "storyboard"
    manifest_path = page_dir / "manifest.json"
    html_path = page_dir / "index.html"
    if not manifest_path.is_file() or not html_path.is_file():
        raise AuthoringError(
            "storyboard page missing; run course-control storyboard-page --lesson "
            + lesson_dir.name
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    html_bytes = html_path.read_bytes()
    if manifest.get("html_sha256") != hashlib.sha256(html_bytes).hexdigest():
        raise AuthoringError("storyboard page changed after it was generated; regenerate it")
    if manifest.get("storyboard_sha256") != _sha(source):
        raise AuthoringError(
            "storyboard changed after the page was built; rebuild the page and review it"
        )
    if (
        str(manifest.get("course_chain_fingerprint") or "")
        != str(chain_fingerprint or "")
    ):
        raise AuthoringError(
            "course plan/card/spec changed after the page was built; "
            "rebuild the page and review it"
        )

    decisions_path = page_dir / "decisions.json"
    if not decisions_path.is_file():
        raise AuthoringError(
            "per-page decisions are missing; run course-control storyboard-review "
            f"--lesson {lesson_dir.name} --approve 1,2,... --by <name>"
        )
    decisions_bytes = decisions_path.read_bytes()
    decisions = json.loads(decisions_bytes.decode("utf-8"))
    if int(decisions.get("schema_version") or 0) != 1:
        raise AuthoringError("decisions.json has no schema_version 1")
    if decisions.get("storyboard_sha256") != manifest.get("storyboard_sha256"):
        raise AuthoringError("decisions were made against a different storyboard; review again")
    if decisions.get("html_sha256") != manifest.get("html_sha256"):
        raise AuthoringError("decisions were made against a different page; review again")
    if (
        str(decisions.get("course_chain_fingerprint") or "")
        != str(chain_fingerprint or "")
    ):
        raise AuthoringError(
            "decisions were made against a different course plan/card/spec; review again"
        )
    if not is_named_approver(decisions.get("reviewed_by")):
        raise AuthoringError(
            "per-page decisions must name the reviewer; run storyboard-review --by"
        )
    rows = decisions.get("pages") or []
    numbers = sorted(int(row.get("page") or 0) for row in rows if isinstance(row, dict))
    if numbers != list(range(1, int(manifest.get("pages") or 0) + 1)):
        raise AuthoringError(
            "decisions must cover every page exactly once; got " + ", ".join(map(str, numbers))
        )
    pending = [str(row.get("page")) for row in rows
               if str(row.get("decision") or "pending") != "approve"]
    if pending:
        raise AuthoringError(
            "storyboard pages not approved: " + ", ".join(pending)
        )
    if manifest.get("missing_captures"):
        raise AuthoringError(
            "storyboard page has no slide captures for pages "
            + ", ".join(map(str, manifest["missing_captures"]))
            + "; capture the slides before signing"
        )
    capture = manifest.get("capture") or {}
    slides_relative = (paths.lesson.content.slides or "slides.md")
    if not capture.get("bound"):
        raise AuthoringError(
            "storyboard page was built from slide captures with no source hash; "
            "run course-control build --lesson "
            + lesson_dir.name
            + " --capture-only, then rebuild the page"
        )
    if capture.get("slides_sha256") != _sha(lesson_dir / slides_relative):
        raise AuthoringError(
            "slide captures no longer match slides.md; recapture and rebuild the page"
        )

    reviewed = lesson_dir / "authoring" / "storyboard-review.html"
    reviewed.parent.mkdir(parents=True, exist_ok=True)
    reviewed.write_bytes(html_bytes)
    reviewed_decisions = lesson_dir / "authoring" / "storyboard-decisions.json"
    reviewed_decisions.write_bytes(decisions_bytes)
    review = {
        "schema_version": 1,
        "lesson": lesson_dir.name,
        "storyboard_path": str(source),
        "storyboard_sha256": manifest["storyboard_sha256"],
        "slides_md_sha256": manifest.get("slides_md_sha256"),
        "capture": capture,
        "course_chain": (
            {
                "course_id": chain.course_id,
                "episode_id": chain.episode_id,
                "lesson_slug": chain.lesson_slug,
                "plan": str(chain.plan) if chain.plan else None,
                "fingerprint": chain.fingerprint,
                "artifacts": chain.artifacts,
            }
            if chain is not None
            else None
        ),
        "course_chain_fingerprint": chain_fingerprint,
        "slides": manifest.get("slides") or [],
        "page_path": "authoring/storyboard-review.html",
        "page_sha256": _sha(reviewed),
        "pages": manifest.get("pages", 0),
        "shots": manifest.get("shots", 0),
        "pages_detail": manifest.get("pages_detail") or [],
        "decisions": decisions.get("pages") or [],
        "decisions_path": "authoring/storyboard-decisions.json",
        "decisions_sha256": _sha(reviewed_decisions),
        "missing_captures": manifest.get("missing_captures") or [],
        "approved_by": approved_by.strip(),
        "approved_at": _now(),
    }
    target = lesson_dir / SIGNOFF_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_json(target, review)
    approve(lesson_dir, SIGNOFF_KIND, SIGNOFF_FILE, approved_by)
    return [SIGNOFF_FILE, "authoring/storyboard-review.html"]


def assert_storyboard_signed(lesson_dir: Path, storyboard_source: Path | None) -> None:
    """The storyboard gate: motion, narration and render need a signed page.

    Fail closed: a missing source, page, hash mismatch or missing approval entry
    blocks.  The page is the durable reviewed artifact, not a build cache.
    """
    if storyboard_source is None:
        return
    lesson_dir = lesson_dir.resolve()
    source = Path(storyboard_source).resolve()
    if not source.is_file():
        raise AuthoringError(f"storyboard source is missing: {source}")
    review_path = lesson_dir / SIGNOFF_FILE
    if not review_path.is_file():
        raise AuthoringError(
            "storyboard page has not been signed; run course-control storyboard-page "
            f"--lesson {lesson_dir.name}, then course-control storyboard-review "
            f"--lesson {lesson_dir.name} --approve 1,2,... --by <name>, then "
            "course-control "
            f"author-accept --lesson {lesson_dir.name} --kind {SIGNOFF_KIND} --by <name>"
        )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    workspace = lesson_dir.parents[1]
    chain = assert_lesson_course_chain(
        workspace,
        lesson_dir,
        config_path=default_chain_config(),
    )
    expected_chain = chain.fingerprint if chain is not None else None
    if (
        str(review.get("course_chain_fingerprint") or "")
        != str(expected_chain or "")
    ):
        raise AuthoringError(
            "course plan/card/spec changed after sign-off; "
            "rebuild the storyboard page and sign it again"
        )
    if not is_named_approver(review.get("approved_by")):
        raise AuthoringError(
            "storyboard sign-off was not made by a named person; sign it again"
        )
    if review.get("storyboard_sha256") != _sha(source):
        raise AuthoringError(
            "storyboard changed after sign-off; rebuild the page and sign it again"
        )
    page_relative = str(review.get("page_path") or "")
    if not page_relative:
        raise AuthoringError("sign-off does not name the reviewed page")
    page = (lesson_dir / page_relative).resolve()
    if not page.is_file():
        raise AuthoringError(f"reviewed storyboard page is missing: {page}")
    if review.get("page_sha256") != _sha(page):
        raise AuthoringError("reviewed storyboard page changed after sign-off")

    decisions_relative = str(review.get("decisions_path") or "")
    if not decisions_relative:
        raise AuthoringError("sign-off does not name the reviewed decisions")
    decisions_path = (lesson_dir / decisions_relative).resolve()
    if not decisions_path.is_file():
        raise AuthoringError(f"reviewed decisions are missing: {decisions_path}")
    if review.get("decisions_sha256") != _sha(decisions_path):
        raise AuthoringError("reviewed decisions changed after sign-off")
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    rows = decisions.get("pages") or []
    numbers = sorted(int(row.get("page") or 0) for row in rows if isinstance(row, dict))
    if numbers != list(range(1, int(review.get("pages") or 0) + 1)):
        raise AuthoringError("reviewed decisions do not cover every page exactly once")
    if any(str(row.get("decision") or "pending") != "approve" for row in rows):
        raise AuthoringError("reviewed decisions contain a rejected or pending page")

    lesson_file = lesson_dir / "lesson.yaml"
    try:
        lesson = yaml.safe_load(lesson_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AuthoringError(f"cannot read lesson for the storyboard gate: {exc}") from exc
    slides_relative = (lesson.get("content") or {}).get("slides") or "slides.md"
    slides_path = lesson_dir / slides_relative
    if review.get("slides_md_sha256") != _sha(slides_path):
        raise AuthoringError("slides.md changed after sign-off; rebuild and sign the page")
    capture = review.get("capture") or {}
    if not capture.get("bound") or capture.get("slides_sha256") != review.get(
        "slides_md_sha256"
    ):
        raise AuthoringError(
            "sign-off is not bound to the slide captures it reviewed; "
            "recapture the slides, rebuild the page and sign again"
        )

    build_root = lesson_dir.parents[1] / "build" / lesson_dir.name
    slides = review.get("slides") or []
    if int(review.get("pages") or 0) > 0 and not slides:
        raise AuthoringError("sign-off records no slide captures; recapture and sign again")
    for item in slides:
        relative = str(item.get("path") or "")
        expected = str(item.get("sha256") or "")
        if not relative or not expected:
            raise AuthoringError("sign-off has an incomplete slide record")
        capture = (build_root / relative).resolve()
        if not capture.is_file():
            raise AuthoringError(f"signed slide capture is missing: {capture}")
        if _sha(capture) != expected:
            raise AuthoringError(f"signed slide capture changed: {capture}")

    assert_approved(lesson_dir, SIGNOFF_FILE)


CONTENT_TARGETS = {
    "slides": "slides.md",
    "notes": "lecture_notes.md",
    "storyboard": "storyboard.yaml",
}


def _write_atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


ACCEPTANCE_KINDS: dict[str, list[tuple[str, str]]] = {
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
    "content": [
        ("slides.md", "slides.md"),
        ("lecture_notes.md", "lecture_notes.md"),
        ("storyboard.yaml", "storyboard.yaml"),
    ],
}


@dataclass
class AcceptancePlan:
    """What one approval will do, decided before anything is written."""

    kind: str
    relative: str
    target: Path
    candidate: Path | None
    current_sha256: str | None
    candidate_sha256: str | None
    action: str
    diff: str = ""


def _diff_summary(old: str, new: str, limit: int = 4) -> str:
    if old == new:
        return "identical"
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0))
    body = [
        line
        for line in lines[2:]
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    added = sum(1 for line in body if line.startswith("+"))
    removed = sum(1 for line in body if line.startswith("-"))
    head = body[:limit]
    summary = f"+{added}/-{removed} lines"
    return summary + ("; " + " | ".join(head) if head else "")


def _digest_problem(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        return "must be a 64-character hex SHA-256 digest"
    return None


def plan_acceptance(
    workspace: Path,
    lesson_dir: Path,
    kind: str,
    *,
    source: str = "candidate",
    expect_sha256: str | None = None,
    force_replace: bool = False,
) -> list[AcceptancePlan]:
    """Decide what an approval would change, without writing anything.

    ``source="current"`` approves the file that is in the lesson right now.
    ``source="candidate"`` promotes the generated draft, but only when the
    target has not changed since the draft was generated; a stale draft would
    silently undo a hand edit, so it is refused unless ``force_replace``.
    """
    if source not in {"candidate", "current"}:
        raise AuthoringError(f"unknown acceptance source: {source}")
    problem = _digest_problem(expect_sha256)
    if problem:
        raise AuthoringError(f"--expect-sha256 {problem}")
    if kind not in ACCEPTANCE_KINDS:
        raise AuthoringError(f"unknown approval kind: {kind}")
    pairs = ACCEPTANCE_KINDS[kind]
    primary = pairs[0][1]
    directory = candidate_dir(workspace, lesson_dir, create=False)
    record = _candidate_record(directory)
    recorded = record.get("files") or {}
    lesson_dir = lesson_dir.resolve()
    plans: list[AcceptancePlan] = []
    for candidate_name, relative in pairs:
        target = lesson_dir / relative
        current = _sha(target) if target.is_file() else None
        if (
            expect_sha256 is not None
            and relative == primary
            and current != expect_sha256
        ):
            raise AuthoringError(
                f"current {relative} is {current or 'missing'}, not "
                f"{expect_sha256}; the file changed, refusing to approve it"
            )
        if source == "current":
            if current is None:
                raise AuthoringError(f"cannot approve a missing file: {target}")
            plans.append(
                AcceptancePlan(
                    kind, relative, target, None, current, None, "approve-current"
                )
            )
            continue
        candidate = directory / candidate_name
        if not candidate.is_file():
            # A digest and a hand-written content file have no draft; approving
            # the current file is the only meaning those kinds have.
            if current is None:
                raise AuthoringError(f"candidate missing: {candidate_name}")
            plans.append(
                AcceptancePlan(
                    kind, relative, target, None, current, None, "approve-current"
                )
            )
            continue
        candidate_sha = _sha(candidate)
        entry = recorded.get(candidate_name)
        if isinstance(entry, dict):
            if entry.get("target_sha256") != current and not force_replace:
                raise AuthoringError(
                    f"refusing to replace {relative}: it changed after this candidate "
                    f"was generated ({str(entry.get('target_sha256'))[:12]} -> "
                    f"{str(current)[:12]}); approve the current file with "
                    "--source current, or pass --force-replace"
                )
        elif kind != "digest" and not force_replace:
            raise AuthoringError(
                f"candidate {candidate_name} has no generation record; approve the "
                "current file with --source current, or pass --force-replace"
            )
        if candidate_sha == current:
            action = "unchanged"
        elif current is None:
            action = "create"
        else:
            action = "replace"
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        new = candidate.read_text(encoding="utf-8")
        plans.append(
            AcceptancePlan(
                kind,
                relative,
                target,
                candidate,
                current,
                candidate_sha,
                action,
                _diff_summary(old, new),
            )
        )
    return plans


def apply_acceptance(
    workspace: Path,
    lesson_dir: Path,
    kind: str,
    approved_by: str,
    *,
    source: str = "candidate",
    expect_sha256: str | None = None,
    force_replace: bool = False,
    dry_run: bool = False,
) -> list[AcceptancePlan]:
    """Plan, then (unless dry-run) write and approve."""
    if not is_named_approver(approved_by):
        raise AuthoringError(f"approval must name a person, not {approved_by!r}")
    if kind == SIGNOFF_KIND:
        if dry_run or source != "candidate" or expect_sha256 or force_replace:
            raise AuthoringError(
                "the storyboard gate is signed with storyboard-review followed by "
                "author-accept --kind storyboard-page; it has no current/candidate choice"
            )
        sign_storyboard_page(workspace, lesson_dir, approved_by)
        return [
            AcceptancePlan(
                kind,
                SIGNOFF_FILE,
                lesson_dir.resolve() / SIGNOFF_FILE,
                None,
                _sha(lesson_dir.resolve() / SIGNOFF_FILE),
                None,
                "signed",
            )
        ]
    plans = plan_acceptance(
        workspace,
        lesson_dir,
        kind,
        source=source,
        expect_sha256=expect_sha256,
        force_replace=force_replace,
    )
    if dry_run:
        return plans
    lesson_dir = lesson_dir.resolve()
    for plan in plans:
        if plan.candidate is not None and plan.action in {"replace", "create"}:
            _write_atomic_text(
                plan.target, plan.candidate.read_text(encoding="utf-8")
            )
    if kind == "content":
        for plan in plans:
            approve(lesson_dir, "content", plan.relative, approved_by)
    else:
        approve(lesson_dir, kind, plans[0].relative, approved_by)
    return plans


def accept_artifact(
    workspace: Path, lesson_dir: Path, kind: str, approved_by: str
) -> list[str]:
    """Copy a candidate artifact into lessons/<slug>/authoring and approve it."""
    plans = apply_acceptance(workspace, lesson_dir, kind, approved_by)
    return [plan.relative for plan in plans]


def accept_content(workspace: Path, lesson_dir: Path, approved_by: str) -> list[str]:
    """Promote approved candidate content into lessons/<slug>/."""
    plans = apply_acceptance(workspace, lesson_dir, "content", approved_by)
    return [plan.relative for plan in plans]
