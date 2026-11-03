from __future__ import annotations

import hashlib
import json
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ai_runtime import TaskRecord, TaskStore
from ai_runtime.tasks import now as task_now

from .config import WorkflowConfig

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class Job:
    job_id: str
    root: Path

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def image(self) -> Path:
        return self.input_dir / "input.png"

    @property
    def original(self) -> Path:
        originals = sorted(self.input_dir.glob("original.*"))
        return originals[0] if originals else self.image

    @property
    def visual_analysis(self) -> Path:
        return self.root / "visual_analysis.json"

    @property
    def model_plan(self) -> Path:
        return self.root / "model_plan.json"

    @property
    def script(self) -> Path:
        return self.root / "build_model.py"

    @property
    def scene_dir(self) -> Path:
        return self.root / "scene"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def validation(self) -> Path:
        return self.root / "validation.json"

    @property
    def revision(self) -> Path:
        return self.root / "revision.json"

    @property
    def metadata(self) -> Path:
        return self.root / "job.json"

    @property
    def tasks_dir(self) -> Path:
        return self.root / "tasks"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"job artifact not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value.lower()[:60] or "model"


def prepare_image(source: Path, target: Path, max_edge: int = 1280) -> None:
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"unsupported image type: {source.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target.parent / f"original{source.suffix.lower()}")
    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        scale = min(1.0, max_edge / max(width, height))
        if scale < 1.0:
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.LANCZOS,
            )
        image.save(target, format="PNG", optimize=True)


def create_job(
    config: WorkflowConfig,
    image: Path,
    *,
    job_id: str | None = None,
    notes: str | None = None,
) -> Job:
    if not image.is_file():
        raise FileNotFoundError(f"image not found: {image}")
    identifier = job_id or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slug(image.stem)}"
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$", identifier):
        raise ValueError("job id must use letters, digits, dot, dash, underscore")
    job = Job(identifier, config.jobs_dir / identifier)
    if job.root.exists():
        raise FileExistsError(f"job already exists: {job.root}")
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job.scene_dir.mkdir(parents=True, exist_ok=True)
    prepare_image(image, job.image)
    write_json(
        job.metadata,
        {
            "schema_version": 1,
            "job_id": identifier,
            "created_at": _now(),
            "source_image": str(image.resolve()),
            "image_sha256": sha256(job.image),
            "notes": notes,
            "stages": {},
        },
    )
    return job


def load_job(config: WorkflowConfig, job_id: str) -> Job:
    job = Job(job_id, config.jobs_dir / job_id)
    if not job.root.is_dir():
        raise FileNotFoundError(f"job not found: {job.root}")
    return job


def update_metadata(job: Job, *, stage: str, **values) -> None:
    data = read_json(job.metadata) if job.metadata.is_file() else {}
    stages = data.setdefault("stages", {})
    entry = stages.setdefault(stage, {})
    entry.update(values)
    entry["updated_at"] = _now()
    write_json(job.metadata, data)


def stage_status(job: Job, stage: str) -> str | None:
    if not job.metadata.is_file():
        return None
    return (read_json(job.metadata).get("stages", {}).get(stage) or {}).get("status")


SUCCESS_STAGES = {"pass", "completed", "fallback"}


def stage_done(job: Job, stage: str, artifact: Path, resume: bool) -> bool:
    """True when --resume can skip a stage with a valid artifact on disk."""
    return bool(resume) and stage_status(job, stage) in SUCCESS_STAGES and Path(artifact).is_file()


def task_store(config: WorkflowConfig) -> TaskStore:
    return TaskStore(config.runtime.task_root_resolved)


def save_task(config: WorkflowConfig, job: Job, record: TaskRecord) -> None:
    """Persist a task record globally and inside the job directory."""
    task_store(config).save(record)
    TaskStore(job.tasks_dir).save(record)


@contextmanager
def stage_task(
    job: Job,
    config: WorkflowConfig,
    *,
    stage: str,
    task_type: str,
    model_key: str,
    input_artifacts: list[str],
    output_artifacts: list[str],
    context_budget: dict | None = None,
    timeout_s: int = 900,
):
    """Track one model stage through running → completed / failed (FR-10)."""
    record = TaskRecord(
        task_id=f"modeling-{job.job_id}-{stage}",
        task_type=task_type,
        assigned_model=config.model(model_key).alias,
        status="running",
        input_artifacts=list(input_artifacts),
        output_artifacts=list(output_artifacts),
        context_budget=dict(context_budget or {}),
        timeout_s=timeout_s,
    )
    record.started_at = task_now()
    save_task(config, job, record)
    update_metadata(job, stage=stage, status="running", task_id=record.task_id)
    try:
        yield record
    except BaseException as exc:  # noqa: BLE001 - persist any failure, then re-raise
        record.status = "failed"
        record.error = f"{type(exc).__name__}: {exc}"
        record.finished_at = task_now()
        save_task(config, job, record)
        update_metadata(
            job, stage=stage, status="failed", task_id=record.task_id, error=record.error
        )
        raise
    else:
        record.status = "completed"
        record.finished_at = task_now()
        save_task(config, job, record)
        current = stage_status(job, stage)
        if current not in {"pass", "fallback", "blocked"}:
            update_metadata(
                job,
                stage=stage,
                status="completed",
                task_id=record.task_id,
                context_budget=record.context_budget,
            )
        else:
            update_metadata(job, stage=stage, task_id=record.task_id)
