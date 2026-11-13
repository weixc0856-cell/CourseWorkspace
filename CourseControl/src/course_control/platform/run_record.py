"""Run records: one file per production run, with stage history inline.

``runtime/runs/<run-id>/run.json`` is the only state file for a run.  Stages
live inside it rather than in a second ``stages.json``, because two files that
describe the same thing eventually disagree.  The file is written atomically
after every stage transition, so an interrupted run leaves the last known state.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.platform.atomic import write_json_atomic
from course_control.platform.workspace_layout import runtime_root

DEFAULT_STAGES = (
    "ingest",
    "understand",
    "plan",
    "author",
    "direct",
    "produce",
    "verify",
    "deliver",
)

StageStatus = Literal["pending", "running", "pass", "fail", "skipped", "blocked"]
RunStatus = Literal["running", "completed", "failed", "stopped"]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class RunStage(StrictModel):
    name: str
    status: StageStatus = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    inputs: list[str] = []
    outputs: list[str] = []
    reason: str | None = None


class RunRecord(StrictModel):
    schema_version: Literal[1] = 1
    run_id: str
    project_id: str
    mode: Literal["course", "topic_video"]
    autonomy: Literal["A0", "A1", "A2", "A3"] = "A1"
    status: RunStatus = "running"
    started_at: str
    finished_at: str | None = None
    stages: list[RunStage] = []


def run_dir(workspace: Path, run_id: str) -> Path:
    return runtime_root(workspace) / "runs" / run_id


def run_path(workspace: Path, run_id: str) -> Path:
    return run_dir(workspace, run_id) / "run.json"


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def new_run(
    workspace: Path,
    project_id: str,
    mode: Literal["course", "topic_video"],
    *,
    autonomy: Literal["A0", "A1", "A2", "A3"] = "A1",
    stages: tuple[str, ...] = DEFAULT_STAGES,
) -> tuple[RunRecord, Path]:
    record = RunRecord(
        run_id=new_run_id(),
        project_id=project_id,
        mode=mode,
        autonomy=autonomy,
        started_at=_now(),
        stages=[RunStage(name=name) for name in stages],
    )
    path = save_run(record, run_path(workspace, record.run_id))
    return record, path


def save_run(record: RunRecord, path: Path) -> Path:
    write_json_atomic(path, record.model_dump(mode="json"))
    return path


def load_run(workspace: Path, run_id: str) -> RunRecord | None:
    path = run_path(workspace, run_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return RunRecord.model_validate(data)


def update_stage(
    record: RunRecord,
    name: str,
    status: StageStatus,
    *,
    reason: str | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> RunRecord:
    """Move one stage; unknown stages are rejected rather than invented."""
    stages: list[RunStage] = []
    found = False
    for stage in record.stages:
        if stage.name != name:
            stages.append(stage)
            continue
        found = True
        now = _now()
        stages.append(
            stage.model_copy(
                update={
                    "status": status,
                    "reason": reason if reason is not None else stage.reason,
                    "inputs": list(inputs) if inputs is not None else stage.inputs,
                    "outputs": list(outputs) if outputs is not None else stage.outputs,
                    "started_at": stage.started_at or now,
                    "finished_at": now if status not in {"pending", "running"} else None,
                }
            )
        )
    if not found:
        raise KeyError(f"unknown run stage: {name}")
    return record.model_copy(update={"stages": stages})


def finish_run(record: RunRecord, status: RunStatus = "completed") -> RunRecord:
    return record.model_copy(update={"status": status, "finished_at": _now()})


def next_pending(record: RunRecord) -> RunStage | None:
    for stage in record.stages:
        if stage.status in {"pending", "running"}:
            return stage
    return None


__all__ = [
    "DEFAULT_STAGES",
    "RunStage",
    "RunRecord",
    "run_dir",
    "run_path",
    "new_run",
    "save_run",
    "load_run",
    "update_stage",
    "finish_run",
    "next_pending",
]
