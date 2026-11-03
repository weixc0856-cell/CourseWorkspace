from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import Status


@dataclass
class StageOutcome:
    name: str
    status: Status
    outputs: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reason: str | None = None
    duration_ms: int = 0
