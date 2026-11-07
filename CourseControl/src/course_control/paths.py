from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from .contracts import LessonConfig, SLUG_RE, ShotSpec, Storyboard

DRIVE_RE = re.compile(r"^[A-Za-z]:")


class ContractError(RuntimeError):
    pass


def path_problem(value: str, *, allow_dir: bool = False) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "path is empty"
    if "\\" in value:
        return "backslashes are not allowed; use /"
    if value.startswith("/") or value.startswith("//") or DRIVE_RE.match(value):
        return "absolute paths are not allowed"
    candidate = value[:-1] if allow_dir and value.endswith("/") else value
    if not candidate:
        return "path is empty"
    parts = candidate.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "path contains empty, '.' or '..' segments"
    return None


def is_under(base: Path, path: Path) -> bool:
    try:
        base_resolved = base.resolve()
        path_resolved = path.resolve()
    except OSError:
        return False
    return path_resolved == base_resolved or base_resolved in path_resolved.parents


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ContractError(f"file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"YAML root must be a mapping: {path}")
    return data


def format_validation_error(exc: ValidationError, source: str) -> str:
    lines = [f"{source} does not match the contract:"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


@dataclass
class LessonPaths:
    workspace: Path
    lesson_dir: Path
    lesson: LessonConfig
    storyboard: Storyboard

    @classmethod
    def load(cls, workspace: Path, lesson_dir: Path) -> "LessonPaths":
        workspace = workspace.resolve()
        lesson_dir = lesson_dir.resolve()
        lesson_file = lesson_dir / "lesson.yaml"
        raw = load_yaml(lesson_file)
        try:
            lesson = LessonConfig.model_validate(raw)
        except ValidationError as exc:
            raise ContractError(format_validation_error(exc, str(lesson_file))) from exc
        if lesson.lesson_id != lesson_dir.name:
            raise ContractError(
                f"lesson_id '{lesson.lesson_id}' does not match directory '{lesson_dir.name}'"
            )
        storyboard_file = lesson_dir / lesson.content.storyboard
        raw_story = load_yaml(storyboard_file)
        try:
            storyboard = Storyboard.model_validate(raw_story)
        except ValidationError as exc:
            raise ContractError(format_validation_error(exc, str(storyboard_file))) from exc
        if storyboard.lesson != lesson.lesson_id:
            raise ContractError(
                f"storyboard.lesson '{storyboard.lesson}' does not match lesson_id"
            )
        return cls(workspace, lesson_dir, lesson, storyboard)

    @property
    def slug(self) -> str:
        return self.lesson.lesson_id

    @property
    def build_root(self) -> Path:
        return self.workspace / "build" / self.slug

    def content_path(self, relative: str) -> Path:
        return (self.lesson_dir / relative).resolve()

    def build_path(self, relative: str) -> Path:
        return (self.build_root / relative).resolve()

    def engine_root(self, engine: str) -> Path:
        roots = {
            "motion_canvas": "MotionStudio",
            "manim": "ManimSandbox",
            "blender": "BlenderStudio",
            "code_video": "CodeVideoStudio",
        }
        try:
            return (self.workspace / roots[engine]).resolve()
        except KeyError as exc:
            raise ContractError(f"unknown engine: {engine}") from exc

    def scene_path(self, shot: ShotSpec) -> tuple[Path, str | None]:
        scene = shot.scene
        class_name = None
        if shot.engine == "manim" and "::" in scene:
            scene, class_name = scene.split("::", 1)
        return (self.engine_root(shot.engine) / scene).resolve(), class_name

    def blend_task_path(self, shot: ShotSpec) -> Path | None:
        if not shot.blend_task:
            return None
        return (self.engine_root("blender") / shot.blend_task).resolve()

    def narration_path(self, relative: str) -> Path:
        return (self.build_root / "narration" / relative).resolve()

    def base_video_path(self) -> Path | None:
        if not self.lesson.compose.base_video:
            return None
        return self.build_path(self.lesson.compose.base_video)

    def subtitles_path(self) -> Path | None:
        if not self.lesson.subtitles.enabled or not self.lesson.content.subtitles:
            return None
        return self.content_path(self.lesson.content.subtitles)
