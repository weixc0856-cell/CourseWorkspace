"""Preview renders for the four shot engines.

Every engine keeps its scene, camera, lighting, animation and timing.  Preview
only changes the raster, the sampling budget and (for Blender) the output
container.  A preview clip is never a release asset.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.content.production import normalize_source
from course_control.platform.timeouts import resolve_timeout
from course_control.platform.utils import probe_media, run_command, which_command
from course_control.preview.profile import PreviewProfile
from course_control.preview.units import PreviewUnit


@dataclass
class EngineResult:
    unit_id: str
    path: Path | None
    status: str
    duration_ms: int = 0
    key: str | None = None
    warnings: list[str] | None = None
    detail: str | None = None


def _safe(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in value)
    return cleaned[:64] or "shot"


def _sha(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _dir_signature(root: Path) -> str:
    parts: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "node_modules" in path.parts or "out" in path.parts:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        parts.append(f"{path.relative_to(root).as_posix()}:{stat.st_size}:{int(stat.st_mtime)}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _meta_key(unit: PreviewUnit, profile: PreviewProfile, source_key: str) -> str:
    design = json.dumps(unit.design or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(
        "\n".join(
            [
                unit.id,
                str(unit.engine),
                unit.scene or "",
                source_key,
                design,
                profile.width.__str__(),
                profile.height.__str__(),
                str(profile.fps),
                profile.mode.value,
            ]
        ).encode("utf-8")
    ).hexdigest()


def _cached(output: Path, key: str) -> bool:
    meta = output.with_suffix(".meta.json")
    if not output.is_file() or not meta.is_file() or output.stat().st_size == 0:
        return False
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data.get("key") == key


def _write_meta(output: Path, key: str, unit: PreviewUnit, profile: PreviewProfile, duration_ms: int) -> None:
    output.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "key": key,
                "unit": unit.id,
                "engine": unit.engine,
                "scene": unit.scene,
                "profile": profile.as_dict(),
                "duration_ms": duration_ms,
                "mode": profile.mode.value,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _verify(path: Path, profile: PreviewProfile, expected_s: float) -> list[str]:
    warnings: list[str] = []
    info = probe_media(path)
    if info.width and abs(info.width - profile.width) > 2:
        warnings.append(f"width {info.width} != {profile.width}")
    if info.height and abs(info.height - profile.height) > 2:
        warnings.append(f"height {info.height} != {profile.height}")
    if info.fps and abs(info.fps - profile.fps) > 0.02:
        warnings.append(f"fps {info.fps} != {profile.fps}")
    if info.duration and expected_s:
        tolerance = max(1.0, expected_s * 0.10)
        if abs(info.duration - expected_s) > tolerance:
            warnings.append(f"duration {info.duration:.2f}s != {expected_s:.2f}s")
    return warnings


def _manim(paths: LessonPaths, unit: PreviewUnit, profile: PreviewProfile, output: Path) -> EngineResult:
    scene = unit.scene or ""
    class_name = None
    if "::" in scene:
        scene, class_name = scene.split("::", 1)
    scene_path, _root = paths.resolve_engine_path("manim", scene)
    if not scene_path.is_file():
        return EngineResult(unit.id, None, "failed", detail=f"scene not found: {scene_path}")
    if not class_name:
        return EngineResult(unit.id, None, "failed", detail="manim scene must be <file>.py::<Class>")
    source_key = _sha(scene_path) or ""
    key = _meta_key(unit, profile, source_key)
    if _cached(output, key):
        return EngineResult(unit.id, output, "cached", key=key)
    media_dir = paths.build_root / "preview" / "manim-media" / _safe(unit.id)
    started = time.monotonic()
    result = run_command(
        [
            *which_command("uv"),
            "run",
            "manim",
            "render",
            "-r",
            f"{profile.width},{profile.height}",
            "--fps",
            str(profile.fps),
            "--media_dir",
            str(media_dir),
            str(scene_path),
            class_name,
        ],
        paths.engine_home("manim"),
        timeout=resolve_timeout(paths, "render:manim"),
        log_path=paths.build_root / "preview" / "logs" / f"manim-{_safe(unit.id)}.log",
        env={
            "PYTHONPATH": str(paths.engine_home("manim")),
            **(
                {"COURSE_DESIGN_JSON": str(unit.metadata["design_path"])}
                if unit.metadata.get("design_path")
                else {}
            ),
        },
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"manim exited {result.exit_code}: {result.stderr[-1500:]}",
        )
    candidates = sorted(media_dir.glob(f"videos/**/{class_name}.mp4"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"rendered file for {class_name} not found under {media_dir}",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidates[-1], output)
    warnings = _verify(output, profile, unit.duration_s)
    _write_meta(output, key, unit, profile, duration_ms)
    return EngineResult(unit.id, output, "ok", duration_ms=duration_ms, key=key, warnings=warnings)


def _code_video(paths: LessonPaths, unit: PreviewUnit, profile: PreviewProfile, output: Path) -> EngineResult:
    scene = normalize_source("code_video", unit.scene or "")
    spec_path, _root = paths.resolve_engine_path("code_video", scene)
    if not spec_path.is_file():
        return EngineResult(unit.id, None, "failed", detail=f"SPEC not found: {spec_path}")
    project = spec_path.parent
    skill = paths.engine_home("code_video") / "skills" / "code-video" / "scripts" / "capture.mjs"
    if not skill.is_file():
        return EngineResult(unit.id, None, "failed", detail=f"capture script not found: {skill}")
    source_key = _dir_signature(project)
    key = _meta_key(unit, profile, source_key)
    if _cached(output, key):
        return EngineResult(unit.id, output, "cached", key=key)
    temp = paths.build_root / "preview" / "tmp" / f"{_safe(unit.id)}.mp4"
    temp.parent.mkdir(parents=True, exist_ok=True)
    command = [
        *which_command("node"),
        str(skill),
        str(project),
        "--fps",
        str(profile.fps),
        "--size",
        f"{profile.width}x{profile.height}",
        "--out",
        str(temp),
    ]
    if unit.duration_s:
        command.extend(["--dur", str(unit.duration_s)])
        if unit.duration_s > 120:
            command.extend(["--chunk-seconds", "60"])
    capture_json = project / "capture.json"
    if capture_json.is_file():
        try:
            flags = json.loads(capture_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            flags = {}
        if isinstance(flags, dict):
            if flags.get("gpu") is True:
                command.append("--gpu")
            if flags.get("jpeg") is True:
                command.append("--jpeg")
    started = time.monotonic()
    result = run_command(
        command,
        project,
        timeout=resolve_timeout(paths, "render:code_video"),
        log_path=paths.build_root / "preview" / "logs" / f"code-video-{_safe(unit.id)}.log",
        env=(
            {"COURSE_DESIGN_JSON": str(unit.metadata["design_path"])}
            if unit.metadata.get("design_path")
            else None
        ),
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"capture exited {result.exit_code}: {result.stderr[-1500:]}",
        )
    if not temp.is_file():
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"capture produced no file: {temp}",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temp, output)
    warnings = _verify(output, profile, unit.duration_s)
    _write_meta(output, key, unit, profile, duration_ms)
    return EngineResult(unit.id, output, "ok", duration_ms=duration_ms, key=key, warnings=warnings)


def _motion_canvas(paths: LessonPaths, unit: PreviewUnit, profile: PreviewProfile, output: Path) -> EngineResult:
    scene = unit.scene or ""
    scene_path, _root = paths.resolve_engine_path("motion_canvas", scene)
    if not scene_path.is_file():
        return EngineResult(unit.id, None, "failed", detail=f"scene not found: {scene_path}")
    source_key = _sha(scene_path) or ""
    key = _meta_key(unit, profile, source_key)
    if _cached(output, key):
        return EngineResult(unit.id, output, "cached", key=key)
    scene_id = scene_path.stem.replace("_", "-")
    started = time.monotonic()
    result = run_command(
        [
            *which_command("node"),
            "scripts/render-headless.mjs",
            "--scene",
            scene_id,
            "--fps",
            str(profile.fps),
            "--width",
            str(profile.width),
            "--height",
            str(profile.height),
            "--out",
            str(output),
            "--run-root",
            str(paths.build_root / "preview" / "tmp" / "motion-canvas"),
            "--vite-port",
            os.environ.get("MOTION_CANVAS_VITE_PORT", "4173"),
            "--sink-port",
            os.environ.get("MOTION_CANVAS_SINK_PORT", "4174"),
        ],
        paths.engine_root("motion_canvas"),
        timeout=resolve_timeout(paths, "render:motion_canvas"),
        log_path=paths.build_root / "preview" / "logs" / f"motion-canvas-{_safe(unit.id)}.log",
        env=(
            {"COURSE_DESIGN_JSON": str(unit.metadata["design_path"])}
            if unit.metadata.get("design_path")
            else None
        ),
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"headless render exited {result.exit_code}: {result.stderr[-1500:]}",
        )
    if not output.is_file() or output.stat().st_size == 0:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"headless render produced no media: {output}",
        )
    warnings = _verify(output, profile, unit.duration_s)
    _write_meta(output, key, unit, profile, duration_ms)
    return EngineResult(unit.id, output, "ok", duration_ms=duration_ms, key=key, warnings=warnings)


def _blender_task(paths: LessonPaths, unit: PreviewUnit, profile: PreviewProfile) -> tuple[Path | None, str | None]:
    from course_control.rendering.blender_task import BlenderTaskError, load_blender_task

    if not unit.metadata.get("blend_task"):
        # A storyboard shot knows its task; a synthetic unit only has the scene.
        for shot in paths.storyboard.shots:
            if shot.id == unit.id and shot.blend_task:
                unit.metadata["blend_task"] = shot.blend_task
                break
    task_value = unit.metadata.get("blend_task")
    if not task_value:
        return None, "blend_task is not declared for this shot"
    task_path, _root = paths.resolve_engine_path("blender", str(task_value))
    if not task_path.is_file():
        return None, f"blend task not found: {task_path}"
    try:
        ref = load_blender_task(task_path, paths.workspace)
    except BlenderTaskError as exc:
        return None, str(exc)
    payload = dict(ref.payload)
    safe = _safe(unit.id)
    output = f"build/{paths.slug}/blender/preview/{safe}.mp4"
    if ref.version == 1:
        payload["resolution"] = [profile.width, profile.height]
        payload["samples"] = max(1, min(int(payload.get("samples", 16)), 8))
        payload["format"] = "mp4"
        payload["output"] = output
        payload.pop("frame", None)
    else:
        render = dict(payload.get("render") or {})
        render["resolution"] = [profile.width, profile.height]
        render["samples"] = max(1, min(int(render.get("samples", 16)), 8))
        render["format"] = "mp4"
        render["output"] = output
        render.pop("frame", None)
        payload["render"] = render
    target_dir = paths.build_root / "blender" / "preview" / paths.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{safe}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target, None


def _blender(paths: LessonPaths, unit: PreviewUnit, profile: PreviewProfile, output: Path) -> EngineResult:
    task, error = _blender_task(paths, unit, profile)
    if task is None:
        return EngineResult(unit.id, None, "failed", detail=error or "blender task unavailable")
    source_key = _sha(task) or ""
    key = _meta_key(unit, profile, source_key)
    if _cached(output, key):
        return EngineResult(unit.id, output, "cached", key=key)
    started = time.monotonic()
    result = run_command(
        [
            *which_command("powershell"),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(paths.workspace / "scripts" / "blender-render.ps1"),
            "-Lesson",
            paths.slug,
            "-Task",
            str(task),
        ],
        paths.workspace,
        timeout=resolve_timeout(paths, "render:blender"),
        log_path=paths.build_root / "preview" / "logs" / f"blender-{_safe(unit.id)}.log",
        env=(
            {"COURSE_DESIGN_JSON": str(unit.metadata["design_path"])}
            if unit.metadata.get("design_path")
            else None
        ),
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"blender exited {result.exit_code}: {result.stderr[-1500:]}",
        )
    if not output.is_file():
        # Blender writes to the path declared in the task, which is under
        # build/<slug>/blender/preview/.  Move it to the preview unit path.
        try:
            payload = json.loads(task.read_text(encoding="utf-8"))
            declared = payload.get("output") if payload.get("schema_version") == 1 else (
                (payload.get("render") or {}).get("output")
            )
            if declared:
                source = Path(str(declared))
                if not source.is_absolute():
                    source = paths.build_root.parent.parent / source
                if source.is_file():
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
        except (OSError, ValueError, TypeError):
            pass
    if not output.is_file():
        return EngineResult(
            unit.id, None, "failed", duration_ms=duration_ms, key=key,
            detail=f"blender produced no file: {output}",
        )
    warnings = _verify(output, profile, unit.duration_s)
    _write_meta(output, key, unit, profile, duration_ms)
    return EngineResult(unit.id, output, "ok", duration_ms=duration_ms, key=key, warnings=warnings)


def _export_design(paths: LessonPaths, unit: PreviewUnit) -> Path | None:
    if not unit.design:
        return None
    target = paths.build_root / "design" / "engine" / f"{_safe(unit.id)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(unit.design, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    return target


def render_engine_shot(
    paths: LessonPaths,
    unit: PreviewUnit,
    profile: PreviewProfile,
    force: bool = False,
    output_root: Path | None = None,
) -> EngineResult:
    if unit.engine not in {"manim", "code_video", "motion_canvas", "blender"}:
        return EngineResult(unit.id, None, "failed", detail=f"unsupported engine: {unit.engine}")
    output = (output_root or paths.build_root / "preview" / "shot") / f"{_safe(unit.id)}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    design = _export_design(paths, unit)
    if design is not None:
        unit.metadata["design_path"] = str(design)
    if force:
        output.unlink(missing_ok=True)
        output.with_suffix(".meta.json").unlink(missing_ok=True)
    if unit.engine == "manim":
        return _manim(paths, unit, profile, output)
    if unit.engine == "code_video":
        return _code_video(paths, unit, profile, output)
    if unit.engine == "motion_canvas":
        return _motion_canvas(paths, unit, profile, output)
    return _blender(paths, unit, profile, output)


__all__ = ["EngineResult", "render_engine_shot"]
