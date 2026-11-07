"""Persistent model-task records (PRD FR-10).

Every model call creates one record, moves it through ``running`` to a terminal
state, and writes it atomically. Failures are recorded, never swallowed.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "blocked",
    "needs_review",
    "skipped",
)
TERMINAL = {"completed", "failed", "blocked", "needs_review", "skipped"}

SCHEMA_VERSION = 1


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=str(path.parent), suffix=".tmp"
    )
    try:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    assigned_model: str
    provider: str = "local"
    status: str = "pending"
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    context_budget: dict = field(default_factory=dict)
    timeout_s: int = 900
    retry_policy: dict = field(default_factory=lambda: {"max_attempts": 1, "backoff_s": 2})
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown task status: {self.status}")
        if not self.task_id or not self.task_type:
            raise ValueError("task_id and task_type are required")
        if self.provider not in {"local", "remote"}:
            raise ValueError(f"unknown model provider: {self.provider}")

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported task record schema: {data.get('schema_version')}")
        missing = [
            key
            for key in ("task_id", "task_type", "assigned_model", "status")
            if not data.get(key)
        ]
        if missing:
            raise ValueError(f"task record missing fields: {missing}")
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            assigned_model=data["assigned_model"],
            provider=str(data.get("provider") or "local"),
            status=data["status"],
            input_artifacts=list(data.get("input_artifacts") or []),
            output_artifacts=list(data.get("output_artifacts") or []),
            context_budget=dict(data.get("context_budget") or {}),
            timeout_s=int(data.get("timeout_s") or 900),
            retry_policy=dict(data.get("retry_policy") or {"max_attempts": 1, "backoff_s": 2}),
            error=data.get("error"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            schema_version=SCHEMA_VERSION,
        )


class TaskStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def save(self, record: TaskRecord) -> Path:
        target = self.path(record.task_id)
        _atomic_write(target, record.as_dict())
        return target

    def load(self, task_id: str) -> TaskRecord:
        return TaskRecord.from_dict(json.loads(self.path(task_id).read_text(encoding="utf-8")))

    def list(self) -> list[TaskRecord]:
        if not self.root.is_dir():
            return []
        records = []
        for path in sorted(self.root.glob("*.json")):
            try:
                records.append(TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (ValueError, OSError):
                continue
        return records

    def run(
        self,
        record: TaskRecord,
        action: Callable[[], dict | None],
    ) -> TaskRecord:
        """Run ``action`` while maintaining the record lifecycle.

        ``action`` may return extra fields (for example ``output_artifacts``).
        Any exception marks the record ``failed`` and is re-raised.
        """
        record.status = "running"
        record.started_at = now()
        record.finished_at = None
        record.error = None
        self.save(record)
        try:
            extra = action() or {}
        except BaseException as exc:  # noqa: BLE001 - persist any failure, then re-raise
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            record.finished_at = now()
            self.save(record)
            raise
        record.status = "completed"
        record.finished_at = now()
        for key, value in extra.items():
            if hasattr(record, key):
                setattr(record, key, value)
        self.save(record)
        return record


def schema() -> dict:
    """JSON Schema for task records (single source of truth for documentation)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ModelTaskRecord",
        "type": "object",
        "required": [
            "schema_version",
            "task_id",
            "task_type",
            "assigned_model",
            "status",
            "input_artifacts",
            "output_artifacts",
            "context_budget",
            "timeout_s",
            "retry_policy",
        ],
        "additionalProperties": False,
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "task_id": {"type": "string", "minLength": 1},
            "task_type": {"type": "string", "minLength": 1},
            "assigned_model": {"type": "string", "minLength": 1},
            "provider": {"enum": ["local", "remote"]},
            "status": {"enum": list(STATUSES)},
            "input_artifacts": {"type": "array", "items": {"type": "string"}},
            "output_artifacts": {"type": "array", "items": {"type": "string"}},
            "context_budget": {"type": "object"},
            "timeout_s": {"type": "integer", "minimum": 1},
            "retry_policy": {"type": "object"},
            "error": {"type": ["string", "null"]},
            "started_at": {"type": ["string", "null"]},
            "finished_at": {"type": ["string", "null"]},
        },
    }
