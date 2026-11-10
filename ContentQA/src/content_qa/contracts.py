from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["supported", "unsupported", "disputed", "needs_human_review", "not_checked"]
RunStatus = Literal["completed", "blocked", "failed"]
TaskStatus = Literal["completed", "failed", "blocked", "skipped"]


class Finding(BaseModel):
    """One candidate claim from the online model. Never a final decision."""

    model_config = ConfigDict(extra="ignore")

    slide: int = Field(ge=1)
    claim: str = Field(min_length=1, max_length=2000)
    verdict: Verdict = "needs_human_review"
    rationale: str = ""
    source_refs: list[str] = Field(default_factory=list)


class ModelReply(BaseModel):
    model_config = ConfigDict(extra="ignore")

    findings: list[Finding] = Field(default_factory=list)


class ReviewTask(BaseModel):
    task_id: str
    slide: int
    status: TaskStatus
    estimated_input_tokens: int = 0
    error: str | None = None


class ReviewReport(BaseModel):
    schema_version: Literal[1] = 1
    run_id: str = ""
    lesson: str
    generated_at: str
    model: str
    base_url: str
    status: RunStatus
    tasks: list[ReviewTask] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
