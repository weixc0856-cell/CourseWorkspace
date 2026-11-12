"""One entry point for Blender task files.

Two generations exist and both stay:

* ``schema_version: 1`` - course shot tasks under ``BlenderStudio/tasks/<lesson>/``.
  They render a pre-authored ``.blend`` to a video or a PNG sequence.
* ``schema_version: 2`` - scene-system tasks under
  ``BlenderStudio/tasks/scene-system/``.  They describe a scene in IR and build
  the ``.blend`` from it.

The generations are not interchangeable, but they must not be guessed by file
location.  This loader validates the envelope, rejects unknown fields, checks
that output paths stay under ``build/<lesson>/blender/``, and dispatches to the
right contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .blender_scene import BlenderSceneTask, SceneContractError, validate_scene_task
from .workspace_layout import build_root_for, content_root


class BlenderTaskError(ValueError):
    pass


class CourseTaskV1(BaseModel):
    """A v1 course shot: render an existing .blend."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    lesson: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    scene: str = Field(min_length=1)
    engine: Literal["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES", "WORKBENCH"]
    resolution: tuple[int, int]
    fps: int = Field(gt=0, le=240)
    frames: int = Field(gt=0)
    samples: int = Field(default=16, ge=1, le=4096)
    format: Literal["mp4", "png"] = "mp4"
    output: str = Field(min_length=1)
    blend: str = Field(min_length=1)
    # Optional PNG sequence frame; ignored for mp4.
    frame: int | None = Field(default=None, ge=1)

    @field_validator("scene")
    @classmethod
    def _scene_slug(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scene must not be blank")
        return value

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: tuple[int, int]) -> tuple[int, int]:
        width, height = value
        if width <= 0 or height <= 0:
            raise ValueError("resolution must be positive")
        if width > 8192 or height > 8192:
            raise ValueError("resolution must be <= 8192")
        return value


@dataclass
class BlenderTaskRef:
    version: int
    path: Path
    payload: dict
    output: Path
    blend: Path | None

    @property
    def lesson(self) -> str:
        return str(self.payload.get("lesson") or "")


def _check_relative(value: str, label: str) -> None:
    if "\\" in value:
        raise BlenderTaskError(f"{label} must use forward slashes")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise BlenderTaskError(f"{label} must be workspace-relative")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise BlenderTaskError(f"{label} contains empty, '.' or '..' segments")


def _resolve_under_workspace(workspace: Path, value: str, label: str) -> Path:
    _check_relative(value, label)
    base = content_root(workspace) if value.startswith("build/") else workspace
    candidate = (base / value).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise BlenderTaskError(f"{label} must stay inside the workspace") from exc
    return candidate


def _validate_v1(task: CourseTaskV1, workspace: Path) -> BlenderTaskRef:
    output = _resolve_under_workspace(workspace, task.output, "output")
    expected_root = build_root_for(workspace, task.lesson) / "blender"
    if expected_root not in output.parents and output.parent != expected_root:
        raise BlenderTaskError(
            f"output must be under build/{task.lesson}/blender/, got {task.output}"
        )
    if task.format == "mp4" and output.suffix.lower() != ".mp4":
        raise BlenderTaskError("format=mp4 requires an .mp4 output")
    if task.format == "png" and output.suffix.lower() != ".png":
        raise BlenderTaskError("format=png requires a .png output")
    blend = _resolve_under_workspace(workspace, task.blend, "blend")
    if blend.suffix.lower() != ".blend":
        raise BlenderTaskError("blend must end with .blend")
    if task.frame is not None and task.frame > task.frames:
        raise BlenderTaskError("frame must be <= frames")
    return BlenderTaskRef(1, Path(), task.model_dump(mode="json"), output, blend)


def load_blender_task(path: Path, workspace: Path) -> BlenderTaskRef:
    path = Path(path)
    workspace = workspace.resolve()
    if not path.is_file():
        raise BlenderTaskError(f"Blender task not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BlenderTaskError(f"cannot read Blender task {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BlenderTaskError("Blender task root must be an object")
    version = data.get("schema_version")
    if version == 1:
        try:
            task = CourseTaskV1.model_validate(data)
        except ValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            raise BlenderTaskError(f"v1 task does not match the contract: {detail}") from exc
        ref = _validate_v1(task, workspace)
    elif version == 2:
        try:
            task = validate_scene_task(data, workspace)
        except SceneContractError as exc:
            raise BlenderTaskError(str(exc)) from exc
        output = _resolve_under_workspace(workspace, task.render.output, "render.output")
        blend = (
            _resolve_under_workspace(workspace, task.render.save_blend, "render.save_blend")
            if task.render.save_blend
            else None
        )
        ref = BlenderTaskRef(2, Path(), task.model_dump(mode="json"), output, blend)
    else:
        raise BlenderTaskError(
            f"unsupported Blender schema_version={version!r}; supported: 1 (course shot), 2 (scene IR)"
        )
    ref.path = path.resolve()
    if ref.lesson and ref.lesson != path.parent.name and version == 1:
        # v1 tasks live in tasks/<lesson>/, so a mismatch is a real authoring bug.
        raise BlenderTaskError(
            f"task lesson '{ref.lesson}' does not match directory '{path.parent.name}'"
        )
    return ref


__all__ = [
    "BlenderTaskError",
    "BlenderTaskRef",
    "CourseTaskV1",
    "load_blender_task",
]
