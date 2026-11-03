from __future__ import annotations

from pathlib import Path

from .config import PROJECT_ROOT, WorkflowConfig
from .job import Job, update_metadata
from .process import run_command
from .script_guard import guard_script

EXECUTE_SCRIPT = PROJECT_ROOT / "blender" / "scripts" / "execute_build.py"


class BuildError(RuntimeError):
    pass


def build_model(config: WorkflowConfig, job: Job) -> dict:
    if not job.script.is_file():
        raise BuildError(f"generated script not found: {job.script}")
    if not job.model_plan.is_file():
        raise BuildError(f"model plan not found: {job.model_plan}")
    code = job.script.read_text(encoding="utf-8")
    guard_script(code)

    job.scene_dir.mkdir(parents=True, exist_ok=True)
    log_path = job.logs_dir / "blender-build.log"
    command = [
        str(Path(config.blender.executable)),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(EXECUTE_SCRIPT),
        "--",
        "--script",
        str(job.script),
        "--out-dir",
        str(job.scene_dir),
        "--plan",
        str(job.model_plan),
    ]
    result = run_command(
        command, PROJECT_ROOT, timeout=config.blender.timeout_seconds, log_path=log_path
    )
    if result.exit_code != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise BuildError(f"Blender exited {result.exit_code}; log: {log_path}\n{tail}")

    outputs = {
        "blend": job.scene_dir / "model.blend",
        "glb": job.scene_dir / "model.glb",
        "preview": job.scene_dir / "preview.png",
        "report": job.scene_dir / "scene_report.json",
    }
    fbx = job.scene_dir / "model.fbx"
    if fbx.is_file():
        outputs["fbx"] = fbx
    missing = [name for name, path in outputs.items() if not path.is_file()]
    if missing:
        raise BuildError(f"Blender reported success but outputs are missing: {missing}")
    update_metadata(
        job,
        stage="build",
        status="pass",
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        log=str(log_path),
        outputs={name: str(path) for name, path in outputs.items()},
    )
    return {**outputs, "duration_ms": result.duration_ms, "log": log_path}
