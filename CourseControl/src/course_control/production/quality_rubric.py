from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel


class CheckSpec(StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["auto", "review"]
    rule: str | None = None
    prompt: str | None = None
    severity: Literal["blocking", "warn"] = "blocking"

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "auto" and not self.rule:
            raise ValueError(f"check {self.id}: auto checks need rule")
        if self.kind == "review" and not self.prompt:
            raise ValueError(f"check {self.id}: review checks need prompt")
        return self


class Dimension(StrictModel):
    weight: float = Field(gt=0, le=100)
    checks: list[CheckSpec] = Field(min_length=1)


class QualityRubric(StrictModel):
    schema_version: int = 1
    dimensions: dict[str, Dimension]
    hard_fails: list[str] = Field(min_length=1)
    pass_threshold: float = Field(default=80, gt=0, le=100)

    @model_validator(mode="after")
    def _weights(self):
        total = sum(d.weight for d in self.dimensions.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"dimension weights must sum to 100, got {total}")
        ids = [c.id for d in self.dimensions.values() for c in d.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("check ids must be unique")
        return self


class QualityRubricError(ValueError):
    pass


def load_quality_rubric(path: Path) -> QualityRubric:
    if not path.is_file():
        raise QualityRubricError(f"quality rubric not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return QualityRubric.model_validate(data)
    except QualityRubricError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise QualityRubricError(f"invalid quality rubric {path}: {exc}") from exc
