from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from ..code_video_qc import check_video, contact_sheet
from ..contracts import Status
from ..paths import LessonPaths, is_under
from ..simulation import load_spec, run_simulation, write_data
from ..theme import write_theme_json
from ..vendor import sync_one, uses_three
from ..timeouts import resolve_timeout
from ..utils import run_command, which_command
from .base import StageOutcome, selected


def _project_for(paths: LessonPaths, shot) -> Path:
    scene_path, _ = paths.scene_path(shot)
    return scene_path.parent


CAPTURE_FLAGS = {"gpu": "--gpu", "jpeg": "--jpeg"}


def capture_flags(project: Path) -> list[str]:
    """Optional capture switches from ``capture.json`` next to the shot's SPEC.

    Both switches change the frame pipe, not the page: ``gpu`` rasterises on the
    host GPU instead of SwiftShader and ``jpeg`` writes JPEG frames instead of
    PNG. Each shot that opts in must re-verify determinism on the host (VERIFY.md).
    """
    path = project / "capture.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    unknown = sorted(set(data) - set(CAPTURE_FLAGS) - {"note"})
    if unknown:
        raise ValueError(f"{path.name} has unknown keys: {', '.join(unknown)}")
    return [flag for key, flag in CAPTURE_FLAGS.items() if data.get(key) is True]


def materialize_simulation(workspace: Path, project: Path, inputs: dict | None) -> Path | None:
    """Run SimulationSpec from ShotSpec.inputs and write data into the project."""
    if not inputs:
        return None
    relative = inputs.get("simulation_spec")
    if not relative:
        return None
    spec_path = (workspace / str(relative)).resolve()
    if not is_under(workspace, spec_path):
        raise ValueError(f"simulation_spec is outside the workspace: {relative}")
    if not spec_path.is_file():
        raise FileNotFoundError(f"simulation_spec not found: {spec_path}")
    data = run_simulation(load_spec(spec_path))
    target = project / str(inputs.get("simulation_out", "simulation.json"))
    write_data(data, target)
    return target


def run(paths: LessonPaths) -> StageOutcome:
    shots = [shot for shot in paths.storyboard.shots if selected(paths, shot.id) and shot.engine == "code_video"]
    if not shots:
        return StageOutcome("render:code_video", Status.NOT_APPLICABLE)

    started = time.monotonic()
    build_root = paths.build_root
    fps = paths.lesson.outputs.fps
    width, height = paths.lesson.outputs.resolution
    skill = paths.engine_root("code_video") / "skills" / "code-video" / "scripts" / "capture.mjs"
    outputs: list[Path] = []
    errors: list[str] = []
    warnings: list[str] = []

    if not skill.is_file():
        return StageOutcome(
            "render:code_video",
            Status.FAIL,
            errors=[f"Code2Video capture script not found: {skill}"],
            reason="missing_skill",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    for shot in shots:
        spec_path, _ = paths.scene_path(shot)
        project = _project_for(paths, shot)
        # A declared scene theme is materialised next to the scene so the page
        # can read the same tokens every engine uses.  No theme, no file.
        if getattr(shot, "theme", None):
            try:
                write_theme_json(paths.workspace, project / "theme.json", shot.theme)
            except (OSError, KeyError) as exc:
                errors.append(f"{shot.id}: theme not written: {exc}")
                continue
        verify = project / "VERIFY.md"
        if not spec_path.is_file():
            errors.append(f"{shot.id}: SPEC not found: {spec_path}")
            continue
        if not verify.is_file():
            errors.append(f"{shot.id}: VERIFY.md not found: {verify}")
            continue
        verify_text = verify.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\|\s*fail\s*\|", verify_text, re.I):
            errors.append(f"{shot.id}: VERIFY.md contains a failing must-have")
            continue

        if uses_three(project):
            try:
                vendor_status = sync_one(paths.workspace, project)
                if vendor_status == "copied":
                    warnings.append(f"{shot.id}: copied vendor three.js into the shot")
            except (OSError, FileNotFoundError) as exc:
                errors.append(f"{shot.id}: vendor three.js unavailable: {exc}")
                continue

        try:
            simulated = materialize_simulation(paths.workspace, project, getattr(shot, "inputs", None))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{shot.id}: simulation failed: {exc}")
            continue
        if simulated is not None:
            warnings.append(f"{shot.id}: simulation data {simulated.name}")

        target = build_root / "animation" / f"{project.name}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        sources = [
            path
            for path in project.rglob("*")
            if path.is_file()
            and "node_modules" not in path.parts
            and "out" not in path.parts
        ]
        # The capture script is outside the shot directory but still determines
        # the pixels: changes to it must invalidate the cached capture.
        newest = max(path.stat().st_mtime for path in [*sources, skill])
        if target.is_file() and target.stat().st_mtime >= newest:
            warnings.append(f"{shot.id}: reused cached capture")
        else:
            temp = build_root / "tmp" / "code-video" / f"{project.name}.mp4"
            temp.parent.mkdir(parents=True, exist_ok=True)
            command = [
                *which_command("node"),
                str(skill),
                str(project),
                "--fps",
                str(fps),
                "--size",
                f"{width}x{height}",
                "--out",
                str(temp),
            ]
            if shot.expected_duration_s:
                command.extend(["--dur", str(shot.expected_duration_s)])
                if shot.expected_duration_s > 120:
                    command.extend(["--chunk-seconds", "60"])
            try:
                command.extend(capture_flags(project))
            except ValueError as exc:
                errors.append(f"{shot.id}: {exc}")
                continue
            result = run_command(
                command,
                project,
                timeout=resolve_timeout(paths, "render:code_video"),
                log_path=build_root / "logs" / f"code-video-{shot.id}.log",
            )
            if result.exit_code != 0:
                errors.append(
                    f"{shot.id}: capture exited {result.exit_code}: {result.stderr[-1500:]}"
                )
                continue
            if not temp.is_file():
                errors.append(f"{shot.id}: capture produced no file: {temp}")
                continue
            shutil.copy2(temp, target)

        expected = shot.expected_duration_s
        qc = check_video(
            target,
            width=width,
            height=height,
            fps=float(fps),
            min_duration=expected,
            max_duration=expected,
            audio="0",
            workspace=paths.workspace,
            log_path=build_root / "logs" / f"code-video-{shot.id}-qc.log",
        )
        qc_path = target.with_suffix(".qc.json")
        qc_path.write_text(
            json.dumps(qc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        outputs.append(qc_path)
        warnings.extend(item.get("detail", item["id"]) for item in qc.get("warnings", []))
        if not qc["ok"]:
            failed = [item for item in qc["checks"] if item["status"] == "fail"]
            errors.extend(
                f"{shot.id}: QC {item['id']} {item.get('actual')} != {item.get('expected')}"
                for item in failed
            )
            continue
        contact = target.with_suffix(".contact.jpg")
        try:
            contact_sheet(target, contact, workspace=paths.workspace)
            outputs.append(contact)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{shot.id}: contact sheet failed: {exc}")
        outputs.append(target)

    duration_ms = int((time.monotonic() - started) * 1000)
    if errors:
        return StageOutcome(
            "render:code_video",
            Status.FAIL,
            outputs=outputs,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
        )
    return StageOutcome(
        "render:code_video",
        Status.PASS,
        outputs=outputs,
        warnings=warnings,
        duration_ms=duration_ms,
    )
