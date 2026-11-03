from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import SLUG_RE
from .paths import LessonPaths, path_problem
from .utils import notes_blocks

FOUR_ELEMENTS = ("时长预算", "动画切入", "技术核查", "逐字口播")


@dataclass
class Issue:
    rule: str
    level: str
    message: str


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    def add(self, rule: str, level: str, message: str) -> None:
        self.issues.append(Issue(rule, level, message))

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<pre\b.*?</pre>", "", text, flags=re.S | re.I)
    text = re.sub(r"<code\b.*?</code>", "", text, flags=re.S | re.I)
    return re.sub(r"`[^`]*`", "", text)


def _page_count(slides_text: str) -> int:
    return sum(1 for line in slides_text.splitlines() if line.strip() == "---") + 1


def _asset_references(slides_text: str) -> list[str]:
    refs = re.findall(r'(?:src|href)="([^"]+)"', slides_text)
    refs += re.findall(r"!\[[^\]]*\]\(([^)]+)\)", slides_text)
    return [ref for ref in refs if ref.startswith("/")]


def _check_path(result: ValidationResult, label: str, value: str | None, *, allow_dir: bool = False) -> None:
    if value is None:
        return
    problem = path_problem(value, allow_dir=allow_dir)
    if problem:
        result.add("V-21", "error", f"{label}: {problem} ({value})")


def validate(paths: LessonPaths) -> ValidationResult:
    result = ValidationResult()
    lesson = paths.lesson

    if not SLUG_RE.match(paths.slug) or lesson.lesson_id != paths.lesson_dir.name:
        result.add("V-01", "error", "lesson_id must be a slug and match the directory name")

    content = lesson.content
    required = {
        "slides": paths.content_path(content.slides),
        "notes": paths.content_path(content.notes),
        "storyboard": paths.content_path(content.storyboard),
    }
    for name, path in required.items():
        if not path.is_file():
            result.add("V-02", "error", f"missing {name} file: {path}")
    if lesson.compose.mode == "recording":
        base = paths.base_video_path()
        if base is None:
            result.add("V-02", "error", "recording mode requires compose.base_video")
        elif not base.is_file():
            result.add("V-02", "error", f"base video not found: {base}")
    if content.outline and not paths.content_path(content.outline).is_file():
        result.add("V-02", "error", f"outline not found: {content.outline}")

    _check_path(result, "content.slides", content.slides)
    _check_path(result, "content.notes", content.notes)
    _check_path(result, "content.storyboard", content.storyboard)
    _check_path(result, "content.assets", content.assets, allow_dir=True)
    _check_path(result, "content.outline", content.outline)
    _check_path(result, "content.subtitles", content.subtitles)
    _check_path(result, "compose.base_video", lesson.compose.base_video)
    _check_path(result, "narration.source", lesson.narration.source)
    for shot in paths.storyboard.shots:
        scene = shot.scene.split("::", 1)[0] if shot.engine == "manim" else shot.scene
        _check_path(result, f"shot {shot.id}.scene", scene)
        _check_path(result, f"shot {shot.id}.blend_task", shot.blend_task)

    if result.errors:
        return result

    slides_text = required["slides"].read_text(encoding="utf-8")
    notes_text = required["notes"].read_text(encoding="utf-8")
    pages = _page_count(slides_text)
    blocks = notes_blocks(notes_text)

    if pages != len(blocks):
        result.add("V-03", "error", f"slides has {pages} pages but notes has {len(blocks)} blocks")
    for label, block in blocks:
        missing = [element for element in FOUR_ELEMENTS if element not in block]
        if missing:
            result.add("V-04", "error", f"Slide {label} missing: {', '.join(missing)}")

    for ref in _asset_references(slides_text):
        prefix = f"/lessons/{paths.slug}/assets/"
        if not ref.startswith(prefix):
            result.add("V-05", "error", f"asset path must start with {prefix}: {ref}")
            continue
        target = paths.workspace / ref.lstrip("/")
        if not target.is_file():
            result.add("V-05", "error", f"asset not found: {ref}")

    clean = _strip_code(slides_text)
    if re.search(r"notes?\s*:", clean, re.I):
        result.add("V-06", "error", "slides.md contains Notes:")
    if "<video" in clean.lower():
        result.add("V-06", "error", "slides.md contains <video>")
    if "[ANIMATION" in clean:
        result.add("V-06", "error", "slides.md contains [ANIMATION]")
    if "$$" in clean or re.search(r"(?<!\\)\$[^$\n]+\$", clean):
        result.add("V-06", "error", "slides.md contains $...$ math delimiters")

    ids: set[str] = set()
    for shot in paths.storyboard.shots:
        if shot.id in ids:
            result.add("V-07", "error", f"duplicate shot id: {shot.id}")
        ids.add(shot.id)
        if shot.slide > pages:
            result.add("V-07", "error", f"shot {shot.id} references slide {shot.slide} > {pages}")
        if shot.engine not in lesson.engines:
            result.add("V-07", "error", f"shot {shot.id} engine {shot.engine} not in lesson.engines")

        scene_path, _ = paths.scene_path(shot)
        if not scene_path.is_file():
            result.add("V-08", "error", f"shot {shot.id} scene not found: {scene_path}")
        if shot.engine == "blender" and not shot.blend_task:
            result.add("V-07", "error", f"blender shot {shot.id} requires blend_task")
        if shot.blend_task:
            task_path = paths.blend_task_path(shot)
            if task_path is None or not task_path.is_file():
                result.add("V-08", "error", f"blend task not found: {shot.blend_task}")

    if "motion_canvas" in lesson.engines:
        project_file = paths.engine_root("motion_canvas") / "src" / "project.ts"
        project_text = project_file.read_text(encoding="utf-8") if project_file.is_file() else ""
        for shot in paths.storyboard.shots:
            if shot.engine != "motion_canvas":
                continue
            scene_path, _ = paths.scene_path(shot)
            stem = scene_path.stem
            if stem not in project_text:
                result.add(
                    "V-09",
                    "error",
                    f"motion scene '{stem}' is not registered in src/project.ts",
                )

    return result
