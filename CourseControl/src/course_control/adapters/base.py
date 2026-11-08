from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import Status


def selected(paths, shot_id: str) -> bool:
    """Shot filter for partial renders; mocks without the method select all."""
    checker = getattr(paths, "selects", None)
    return checker(shot_id) if checker is not None else True


@dataclass
class StageOutcome:
    name: str
    status: Status
    outputs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reason: str | None = None
    duration_ms: int = 0
