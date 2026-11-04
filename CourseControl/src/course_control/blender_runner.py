from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image, ImageStat

from .blender_scene import BlenderSceneTask, validate_scene_task
from .paths import ContractError
from .scene_presets import expand_task
from .utils import probe_media, run_command, which_command


class SceneRunError(RuntimeError):
    pass


@dataclass
class Check:
    id: str
    status: str
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SceneRunResult:
    status: str
    manifest_path: Path
    manifest: dict
    checks: list[Check]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tools(workspace: Path) -> tuple[str, int]:
    path = workspace / "config" / "tools.yaml"
    if not path.is_file():
        raise SceneRunError(f"config/tools.yaml not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    blender = data.get("blender") or {}
    executable = str(blender.get("executable") or "")
    if not executable or "<BLENDER_EXE>" in executable:
        raise SceneRunError("config/tools.yaml blender.executable is not configured")
    if not Path(executable).is_file():
        raise SceneRunError(f"Blender executable not found: {executable}")
    timeout = int(blender.get("timeout_seconds", 1800))
    return executable, timeout


def _task_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _blender_version(executable: str, workspace: Path) -> str:
    result = run_command([executable, "--version"], workspace, timeout=60)
    lines = (result.stdout or "").splitlines()
    return lines[0].strip() if lines else "unknown"


def _check_png(path: Path, task: BlenderSceneTask, checks: list[Check]) -> None:
    if not path.is_file():
        checks.append(Check("output.exists", "fail", f"missing: {path}"))
        return
    checks.append(Check("output.exists", "pass", str(path)))
    size = path.stat().st_size
    if size < 1024:
        checks.append(Check("output.size", "fail", f"{size} bytes"))
    else:
        checks.append(Check("output.size", "pass", f"{size} bytes"))
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            expected = tuple(task.render.resolution)
            if (width, height) != expected:
                checks.append(
                    Check("output.resolution", "fail", f"{width}x{height} != {expected[0]}x{expected[1]}")
                )
            else:
                checks.append(Check("output.resolution", "pass", f"{width}x{height}"))
            if task.render.film_transparent:
                checks.append(Check("output.black_frame", "skipped", "film_transparent"))
            else:
                gray = image.convert("L").resize((64, 64))
                mean = ImageStat.Stat(gray).mean[0]
                if mean < 2.0:
                    checks.append(Check("output.black_frame", "fail", f"mean luma {mean:.2f}"))
                else:
                    checks.append(Check("output.black_frame", "pass", f"mean luma {mean:.2f}"))
    except Exception as exc:  # noqa: BLE001 - report any decode failure
        checks.append(Check("output.decode", "fail", str(exc)))


def _check_video(path: Path, task: BlenderSceneTask, checks: list[Check]) -> None:
    if not path.is_file():
        checks.append(Check("output.exists", "fail", f"missing: {path}"))
        return
    checks.append(Check("output.exists", "pass", str(path)))
    try:
        info = probe_media(path)
    except ContractError as exc:
        checks.append(Check("output.probe", "fail", str(exc)))
        return
    checks.append(Check("output.probe", "pass", f"{info.codec} {info.width}x{info.height} {info.duration}s"))
    expected = tuple(task.render.resolution)
    if (info.width, info.height) != expected:
        checks.append(
            Check("output.resolution", "fail", f"{info.width}x{info.height} != {expected[0]}x{expected[1]}")
        )
    else:
        checks.append(Check("output.resolution", "pass", f"{info.width}x{info.height}"))
    fps = task.render.fps or task.scene.fps
    frames = task.scene.frame_end - task.scene.frame_start + 1
    expected_duration = frames / fps
    if info.duration is None:
        checks.append(Check("output.duration", "fail", "duration unavailable"))
    elif abs(info.duration - expected_duration) > max(0.2, 2.0 / fps):
        checks.append(
            Check(
                "output.duration",
                "fail",
                f"{info.duration:.3f}s != expected {expected_duration:.3f}s",
            )
        )
    else:
        checks.append(Check("output.duration", "pass", f"{info.duration:.3f}s"))


def _close(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return abs(float(left) - float(right)) <= tolerance


PRINCIPLED_SOCKETS = {
    "base_color": "Base Color",
    "metallic": "Metallic",
    "roughness": "Roughness",
    "alpha": "Alpha",
    "ior": "IOR",
    "emission_color": "Emission Color",
    "emission_strength": "Emission Strength",
    "coat_weight": "Coat Weight",
    "coat_roughness": "Coat Roughness",
}
EMISSION_SOCKETS = {"color": "Color", "strength": "Strength"}


def _value_matches(expected, actual, tolerance: float = 1e-4) -> bool:
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(expected) != len(actual):
            return False
        return all(
            abs(float(left) - float(right)) <= tolerance
            for left, right in zip(expected, actual)
        )
    if actual is None:
        return False
    return abs(float(actual) - float(expected)) <= tolerance


def _check_declared_materials(
    report: dict, task: BlenderSceneTask, checks: list[Check]
) -> None:
    if not task.materials:
        return
    materials = {entry.get("name"): entry for entry in report.get("materials", [])}
    problems = []
    for spec in task.materials:
        entry = materials.get(spec.id)
        if entry is None:
            problems.append(f"{spec.id}: missing material")
            continue
        if entry.get("shader") != spec.shader:
            problems.append(f"{spec.id}: shader {entry.get('shader')} != {spec.shader}")
            continue
        params = spec.params.model_dump()
        sockets = PRINCIPLED_SOCKETS if spec.shader == "principled" else EMISSION_SOCKETS
        actual_params = entry.get("params", {})
        for field, socket in sockets.items():
            actual = actual_params.get(socket)
            if not _value_matches(params[field], actual):
                problems.append(f"{spec.id}.{field}: {actual!r} != {params[field]!r}")
        if spec.shader == "principled":
            bump = entry.get("bump")
            if params["bump_strength"] > 0.0:
                if bump is None:
                    problems.append(f"{spec.id}: bump nodes missing")
                else:
                    expected_bump = {
                        "strength": params["bump_strength"],
                        "distance": params["bump_distance"],
                        "noise_scale": params["bump_scale"],
                        "noise_detail": params["bump_detail"],
                    }
                    for key, expected in expected_bump.items():
                        if not _value_matches(expected, bump.get(key)):
                            problems.append(
                                f"{spec.id}.{key}: {bump.get(key)!r} != {expected!r}"
                            )
            elif bump is not None:
                problems.append(f"{spec.id}: unexpected bump nodes")
    checks.append(
        Check(
            "scene.materials",
            "fail" if problems else "pass",
            "; ".join(problems) if problems else f"{len(task.materials)} materials match",
        )
    )


def _check_declared_objects(report: dict, task: BlenderSceneTask, checks: list[Check]) -> None:
    report_objects = {entry.get("name"): entry for entry in report.get("objects", [])}

    text_specs = [obj for obj in task.objects if obj.type == "TEXT"]
    if text_specs:
        problems = []
        for spec in text_specs:
            entry = report_objects.get(spec.id, {})
            body = (entry.get("text") or {}).get("body")
            if entry.get("type") != "FONT":
                problems.append(f"{spec.id}: missing FONT object")
            elif body != spec.text.body:
                problems.append(f"{spec.id}: body {body!r} != {spec.text.body!r}")
        checks.append(
            Check(
                "scene.text_objects",
                "fail" if problems else "pass",
                "; ".join(problems) if problems else f"{len(text_specs)} text objects match",
            )
        )

    curve_specs = [obj for obj in task.objects if obj.type == "CURVE"]
    if curve_specs:
        problems = []
        for spec in curve_specs:
            entry = report_objects.get(spec.id, {})
            info = entry.get("curve") or {}
            if entry.get("type") != "CURVE":
                problems.append(f"{spec.id}: missing CURVE object")
                continue
            if info.get("points") != len(spec.curve.points):
                problems.append(
                    f"{spec.id}: points {info.get('points')} != {len(spec.curve.points)}"
                )
            if bool(info.get("cyclic")) != spec.curve.cyclic:
                problems.append(f"{spec.id}: cyclic mismatch")
            if not _close(info.get("bevel_depth", 0.0), spec.curve.bevel_depth):
                problems.append(f"{spec.id}: bevel_depth mismatch")
        checks.append(
            Check(
                "scene.curves",
                "fail" if problems else "pass",
                "; ".join(problems) if problems else f"{len(curve_specs)} curves match",
            )
        )

    camera_specs = task.cameras
    if camera_specs:
        report_cameras = {entry.get("name"): entry for entry in report.get("cameras", [])}
        problems = []
        for spec in camera_specs:
            entry = report_cameras.get(spec.id)
            if entry is None:
                continue
            expected = "ORTHO" if spec.projection == "ORTHO" else "PERSP"
            if entry.get("projection") != expected:
                problems.append(
                    f"{spec.id}: projection {entry.get('projection')} != {expected}"
                )
            if spec.projection == "ORTHO" and not _close(
                entry.get("ortho_scale", 0.0), spec.ortho_scale
            ):
                problems.append(
                    f"{spec.id}: ortho_scale {entry.get('ortho_scale')} != {spec.ortho_scale}"
                )
        checks.append(
            Check(
                "scene.cameras",
                "fail" if problems else "pass",
                "; ".join(problems) if problems else f"{len(camera_specs)} cameras match",
            )
        )


def _scene_checks(report: dict, task: BlenderSceneTask, checks: list[Check]) -> None:
    if not report.get("ok"):
        issues = "; ".join(issue.get("message", "") for issue in report.get("issues", [])[:5])
        checks.append(Check("scene.report", "fail", issues or "scene report not ok"))
    else:
        checks.append(Check("scene.report", "pass", "no issues"))

    camera = report.get("scene", {}).get("active_camera")
    checks.append(
        Check("scene.active_camera", "pass" if camera else "fail", camera or "none")
    )

    expected = len(task.objects) + len(task.cameras) + len(task.lights)
    actual = len(report.get("objects", []))
    if task.base_blend is None:
        ok = actual == expected
        detail = f"{actual} objects (expected {expected})"
    else:
        ok = actual >= expected
        detail = f"{actual} objects (>= {expected} including base blend)"
    checks.append(Check("scene.object_count", "pass" if ok else "fail", detail))

    _check_declared_objects(report, task, checks)
    _check_declared_materials(report, task, checks)

    expected_modifiers = sum(len(obj.geometry_nodes) for obj in task.objects)
    if expected_modifiers:
        actual_modifiers = sum(
            1
            for obj in report.get("objects", [])
            for modifier in obj.get("modifiers", [])
            if modifier.get("type") == "NODES"
        )
        checks.append(
            Check(
                "scene.geometry_nodes",
                "pass" if actual_modifiers >= expected_modifiers else "fail",
                f"{actual_modifiers} node modifiers (expected {expected_modifiers})",
            )
        )

    expected_channels = sum(len(animation.channels) for animation in task.animations)
    if expected_channels:
        actual_channels = sum(
            len(entry.get("channels", [])) for entry in report.get("animations", [])
        )
        checks.append(
            Check(
                "scene.animation",
                "pass" if actual_channels >= expected_channels else "fail",
                f"{actual_channels} f-curves (expected at least {expected_channels})",
            )
        )


def _verify_blend(
    workspace: Path,
    executable: str,
    blend: Path,
    report_path: Path,
    log_path: Path,
    task: BlenderSceneTask,
    checks: list[Check],
) -> dict | None:
    if not blend.is_file():
        checks.append(Check("scene.blend", "fail", f"missing: {blend}"))
        return None
    checks.append(Check("scene.blend", "pass", str(blend)))
    script = workspace / "BlenderStudio" / "scripts" / "verify_scene.py"
    command = [
        executable,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(script),
        "--",
        "--blend",
        str(blend),
        "--json",
        str(report_path),
        "--strict",
    ]
    result = run_command(command, workspace, timeout=300, log_path=log_path)
    if not report_path.is_file():
        checks.append(Check("scene.verify", "fail", f"verify exited {result.exit_code}; no report"))
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _scene_checks(report, task, checks)
    return report


def run_scene_task(
    workspace: Path,
    task_path: Path,
    *,
    verify: bool = True,
) -> SceneRunResult:
    workspace = workspace.resolve()
    task_file = task_path if task_path.is_absolute() else workspace / task_path
    if not task_file.is_file():
        raise SceneRunError(f"task not found: {task_file}")
    source_data = json.loads(task_file.read_text(encoding="utf-8"))
    data, preset_refs = expand_task(source_data, workspace)
    task = validate_scene_task(data, workspace)

    executable, timeout = _tools(workspace)
    output = _resolve(workspace, task.render.output)
    blend = _resolve(workspace, task.render.save_blend) if task.render.save_blend else None
    manifest_dir = workspace / "build" / task.lesson / "blender" / "manifests"
    log_dir = workspace / "build" / task.lesson / "logs"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{task.task_id}.json"
    report_path = manifest_dir / f"{task.task_id}-scene.json"
    execution_task = task_file
    expanded_path = None
    if preset_refs:
        expanded_path = manifest_dir / f"{task.task_id}.expanded.json"
        expanded_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        execution_task = expanded_path

    checks: list[Check] = []
    started_at = _now()
    started = time.monotonic()
    command = [
        *which_command("powershell"),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(workspace / "scripts" / "blender-render.ps1"),
        "-Lesson",
        task.lesson,
        "-Task",
        str(execution_task),
    ]
    result = run_command(
        command,
        workspace,
        timeout=timeout + 300,
        log_path=log_dir / f"scene-run-{task.task_id}.log",
    )
    execute_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        detail = f"exit {result.exit_code}" + (" (timeout)" if result.timed_out else "")
        wrapper_log = log_dir / f"blender-{task_file.stem}.log"
        if wrapper_log.is_file():
            detail += "\n" + wrapper_log.read_text(
                encoding="utf-8-sig", errors="replace"
            )[-1200:]
        else:
            detail += ": " + (result.stderr or result.stdout)[-500:]
        checks.append(Check("execute.exit", "fail", detail))
    else:
        checks.append(Check("execute.exit", "pass", "exit 0"))

    if result.exit_code == 0:
        if task.render.format == "png":
            _check_png(output, task, checks)
        else:
            _check_video(output, task, checks)

        if verify and blend is not None:
            _verify_blend(
                workspace,
                executable,
                blend,
                report_path,
                log_dir / f"verify-{task.task_id}.log",
                task,
                checks,
            )
        elif verify:
            checks.append(Check("scene.verify", "skipped", "no save_blend in task"))

    failed = [check for check in checks if check.status == "fail"]
    status = "fail" if failed else "pass"
    finished_at = _now()

    report = None
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    blender_version = report.get("blender_version") if report else None
    if blender_version is None:
        try:
            blender_version = _blender_version(executable, workspace)
        except Exception:  # noqa: BLE001 - version is metadata only
            blender_version = "unknown"

    manifest = {
        "schema_version": 1,
        "task_id": task.task_id,
        "lesson": task.lesson,
        "status": status,
        "task_file": str(task_file),
        "task_hash": _task_hash(data),
        "source_task_hash": _task_hash(source_data),
        "presets": preset_refs,
        "expanded_task": str(expanded_path) if expanded_path else None,
        "seed": task.scene.seed,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": execute_ms,
        "environment": {
            "blender_executable": executable,
            "blender_version": blender_version,
            "host_python": platform.python_version(),
            "platform": platform.platform(),
        },
        "render": task.render.model_dump(),
        "execute": {
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "log": str(log_dir / f"scene-run-{task.task_id}.log"),
        },
        "verify": {
            "report": str(report_path) if report_path.is_file() else None,
            "scene_ok": report.get("ok") if report else None,
        },
        "outputs": [str(output)],
        "checks": [check.as_dict() for check in checks],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return SceneRunResult(status, manifest_path, manifest, checks)
