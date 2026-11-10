"""Stage checkpoints and top-level build resume.

A checkpoint is only reusable when all of these hold:

* the stage finished with ``pass`` (skips are re-evaluated, not cached);
* the configuration fingerprint is unchanged;
* every recorded input file still has the same SHA-256;
* every recorded output file still exists with the same SHA-256.

Anything else re-runs the stage. A "stage says done" flag is never trusted on
its own: outputs are re-hashed before a stage is skipped.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .atomic import write_json_atomic
from .contracts import Status
from .paths import LessonPaths
from .adapters.base import StageOutcome

STAGE_ORDER = [
    "capture_slides",
    "render:motion_canvas",
    "render:manim",
    "render:blender",
    "render:code_video",
    "collect",
    "compose",
    "burn_subtitles",
    "brand",
    "verify",
]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def hash_files(paths: LessonPaths, files) -> dict[str, str]:
    """Hash files under a stable key (workspace- or build-relative)."""
    result: dict[str, str] = {}
    for path in files:
        path = Path(path)
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
            try:
                key = resolved.relative_to(paths.workspace).as_posix()
            except ValueError:
                key = str(resolved)
        except OSError:
            continue
        digest = sha256_file(path)
        if digest:
            result[key] = digest
    return result


def hash_tree(paths: LessonPaths, root: Path, *, skip: tuple[str, ...] = ()) -> dict[str, str]:
    if not root.is_dir():
        return {}
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        files.append(path)
    return hash_files(paths, files)


def _content_files(paths: LessonPaths, *, subtitles: bool = False) -> list[Path]:
    lesson = paths.lesson
    files = [paths.lesson_dir / "lesson.yaml"]
    files.append(paths.content_path(lesson.content.slides))
    files.append(paths.content_path(lesson.content.notes))
    if lesson.content.outline:
        files.append(paths.content_path(lesson.content.outline))
    if paths.storyboard_source is not None:
        files.append(Path(paths.storyboard_source))
    else:
        files.append(paths.lesson_dir / lesson.content.storyboard)
    if paths.production_source is not None:
        files.append(Path(paths.production_source))
    if subtitles and lesson.content.subtitles:
        files.append(paths.content_path(lesson.content.subtitles))
    return files


def _shot_files(paths: LessonPaths, engine: str) -> list[Path]:
    files: list[Path] = []
    for shot in paths.storyboard.shots:
        if shot.engine != engine:
            continue
        scene, _ = paths.scene_path(shot)
        if engine == "code_video":
            project = scene.parent
            if project.is_dir():
                files.extend(
                    path
                    for path in project.rglob("*")
                    if path.is_file()
                    and "node_modules" not in path.parts
                    and "out" not in path.parts
                    # The per-shot copy is a build artifact; the canonical
                    # vendor file below is the input that matters.
                    and path.name != "three.module.js"
                )
        else:
            files.append(scene)
        blend = paths.blend_task_path(shot)
        if blend is not None:
            files.append(blend)
        inputs = getattr(shot, "inputs", None) or {}
        for key in ("simulation_spec", "data", "dataset"):
            value = inputs.get(key)
            if value:
                candidate = (paths.workspace / str(value)).resolve()
                files.append(candidate)
    return files


def stage_inputs(paths: LessonPaths, stage: str) -> dict[str, str]:
    """Files whose change must invalidate a stage checkpoint."""
    common = _content_files(paths)
    files: list[Path] = list(common)
    subtitle_files: list[Path] = []
    if paths.lesson.content.subtitles:
        subtitle_files.append(paths.content_path(paths.lesson.content.subtitles))
    if stage == "capture_slides":
        files = list(common)
    elif stage.startswith("render:"):
        engine = stage.split(":", 1)[1]
        files = list(common) + _shot_files(paths, engine)
        if engine == "code_video":
            files.append(
                paths.engine_root("code_video")
                / "skills"
                / "code-video"
                / "scripts"
                / "capture.mjs"
            )
            files.append(paths.workspace / "CodeVideoStudio" / "vendor" / "three" / "three.module.js")
        files.append(paths.workspace / "config" / "tools.yaml")
    elif stage == "collect":
        files = list(common) + subtitle_files + [
            paths.build_root / "narration" / "narration.meta.json",
            paths.build_root / "narration" / "narration.wav",
        ]
        inputs = hash_files(paths, files)
        inputs.update(hash_tree(paths, paths.build_root / "animation"))
        inputs.update(hash_tree(paths, paths.build_root / "slides"))
        return inputs
    elif stage == "compose":
        files = list(common) + subtitle_files + [
            paths.build_root / "shots.json",
            paths.build_root / "contracts" / "timeline.spec.json",
        ]
        inputs = hash_files(paths, files)
        inputs.update(hash_tree(paths, paths.build_root / "animation"))
        inputs.update(hash_tree(paths, paths.build_root / "slides"))
        return inputs
    elif stage == "burn_subtitles":
        files = list(common) + subtitle_files + [paths.build_root / "final" / "course-video.mp4"]
    elif stage == "brand":
        files = list(common) + [
            paths.build_root / "final" / "course-video.mp4",
            paths.build_root / "final" / "course-video-mixed.mp4",
            paths.build_root / "brand" / "plan.json",
        ]
    return hash_files(paths, files)


@dataclass
class Checkpoint:
    stage: str
    status: str
    config_fingerprint: str
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    run_id: str = ""
    created_at: str = ""

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "stage": self.stage,
            "status": self.status,
            "config_fingerprint": self.config_fingerprint,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "warnings": self.warnings,
            "run_id": self.run_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            stage=str(data.get("stage") or ""),
            status=str(data.get("status") or ""),
            config_fingerprint=str(data.get("config_fingerprint") or ""),
            inputs=dict(data.get("inputs") or {}),
            outputs=dict(data.get("outputs") or {}),
            warnings=list(data.get("warnings") or []),
            run_id=str(data.get("run_id") or ""),
            created_at=str(data.get("created_at") or ""),
        )


class CheckpointStore:
    def __init__(self, build_root: Path, fingerprint: str):
        self.build_root = build_root.resolve()
        self.root = self.build_root / "runtime" / "checkpoints"
        self.fingerprint = fingerprint

    def _path(self, stage: str) -> Path:
        return self.root / (stage.replace(":", "-") + ".json")

    def load(self, stage: str) -> Checkpoint | None:
        path = self._path(stage)
        if not path.is_file():
            return None
        try:
            return Checkpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def _output_path(self, relative: str) -> Path:
        candidate = Path(relative)
        return candidate if candidate.is_absolute() else (self.build_root / candidate)

    def check(self, stage: str, inputs: dict[str, str]) -> tuple[bool, list[str]]:
        checkpoint = self.load(stage)
        if checkpoint is None:
            return False, ["no checkpoint"]
        if checkpoint.status != Status.PASS.value:
            return False, [f"checkpoint status={checkpoint.status}"]
        if checkpoint.config_fingerprint != self.fingerprint:
            return False, ["configuration fingerprint changed"]
        if checkpoint.inputs != inputs:
            changed = sorted(
                key
                for key in set(checkpoint.inputs) | set(inputs)
                if checkpoint.inputs.get(key) != inputs.get(key)
            )
            return False, ["inputs changed: " + ", ".join(changed[:6])]
        missing: list[str] = []
        for relative, digest in checkpoint.outputs.items():
            path = self._output_path(relative)
            if not path.is_file():
                missing.append(f"missing output: {relative}")
            elif sha256_file(path) != digest:
                missing.append(f"output hash changed: {relative}")
        if missing:
            return False, missing[:6]
        return True, []

    def save(self, outcome: StageOutcome, inputs: dict[str, str], run_id: str) -> Checkpoint:
        outputs: dict[str, str] = {}
        for path in outcome.outputs:
            candidate = Path(path)
            try:
                relative = candidate.resolve().relative_to(self.build_root).as_posix()
            except (OSError, ValueError):
                relative = str(candidate.resolve())
            digest = sha256_file(candidate)
            if digest:
                outputs[relative] = digest
        checkpoint = Checkpoint(
            stage=outcome.name,
            status=outcome.status.value,
            config_fingerprint=self.fingerprint,
            inputs=inputs,
            outputs=outputs,
            warnings=list(outcome.warnings),
            run_id=run_id,
            created_at=_now(),
        )
        write_json_atomic(self._path(outcome.name), checkpoint.as_dict())
        return checkpoint

    def invalidate(self, stage: str) -> None:
        self._path(stage).unlink(missing_ok=True)

    def invalidate_from(self, stage: str) -> None:
        if stage not in STAGE_ORDER:
            return
        for name in STAGE_ORDER[STAGE_ORDER.index(stage) :]:
            self.invalidate(name)


def resumed_outcome(checkpoint: Checkpoint) -> StageOutcome:
    outputs = []
    for relative in checkpoint.outputs:
        path = Path(relative)
        outputs.append(path if path.is_absolute() else path)
    return StageOutcome(
        checkpoint.stage,
        Status.PASS,
        outputs=outputs,
        warnings=[f"resumed from checkpoint {checkpoint.run_id}: {checkpoint.stage}"],
        reason="resumed_from_checkpoint",
    )


def run_stage(
    name: str,
    inputs: dict[str, str],
    action,
    store: CheckpointStore,
    *,
    resume: bool,
    run_id: str = "",
    force: bool = False,
) -> tuple[StageOutcome, bool, list[str]]:
    """Run ``action`` unless a valid checkpoint lets us reuse it.

    Returns ``(outcome, reused, reasons)`` where ``reasons`` explains why a
    checkpoint was not reused.
    """
    reasons: list[str] = []
    if resume and not force:
        valid, reasons = store.check(name, inputs)
        if valid:
            checkpoint = store.load(name)
            assert checkpoint is not None
            return resumed_outcome(checkpoint), True, []
    outcome = action()
    if outcome.status == Status.PASS:
        store.save(outcome, inputs, run_id)
    return outcome, False, reasons


__all__ = [
    "Checkpoint",
    "CheckpointStore",
    "STAGE_ORDER",
    "hash_files",
    "hash_tree",
    "resumed_outcome",
    "run_stage",
    "sha256_file",
    "stage_inputs",
]
