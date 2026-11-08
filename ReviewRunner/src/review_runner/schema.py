"""Data contracts for the review runner.

Every model here describes a local artifact. ``production_effect`` is a fixed
``none``: a review result is a second opinion, not an acceptance decision.
Exit code 0 means "the review ran to completion", never "the code is correct".
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "review-runner/v1"
PRODUCTION_EFFECT = "none"


class ReviewType(str, Enum):
    code = "code"
    docs = "docs"
    course = "course"


class ScopeMode(str, Enum):
    commit = "commit"
    base = "base"


class ExecutionStatus(str, Enum):
    not_run = "NOT_RUN"
    success = "EXECUTION_SUCCESS"
    failed = "EXECUTION_FAILED"


class ReviewStatus(str, Enum):
    not_run = "NOT_RUN"
    completed = "REVIEW_COMPLETED"
    incomplete = "REVIEW_INCOMPLETE"


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    INFO = "INFO"


class Category(str, Enum):
    correctness = "Correctness"
    reliability = "Reliability"
    security = "Security"
    documentation = "Documentation"
    teaching = "Teaching"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Verification(str, Enum):
    unverified = "unverified"
    verified = "verified"
    dismissed = "dismissed"


class Finding(BaseModel):
    """One candidate defect. Every finding starts as ``unverified``.

    The model's own ``confidence`` is recorded but is never evidence of truth;
    a human has to confirm a finding before any fix is attempted.
    """

    severity: Severity
    category: Category
    file: str = Field(min_length=1)
    line: int | None = Field(default=None, ge=1)
    problem: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    suggested_fix: str = Field(min_length=1)
    confidence: Confidence = Confidence.low
    verification: Verification = Verification.unverified

    @field_validator("file")
    @classmethod
    def _no_absolute_paths(cls, value: str) -> str:
        if value.startswith("/") or value.startswith("\\") or ":" in value[:3]:
            raise ValueError("finding.file must be repository-relative")
        return value


class FindingsEnvelope(BaseModel):
    """The parsed findings document. Never carries a verdict."""

    production_effect: Literal["none"] = "none"
    findings: list[Finding]


class FileRecord(BaseModel):
    path: str
    role: Literal["diff", "changed_file", "context", "task_prompt", "manifest"]
    sha256: str
    bytes: int
    tokens_estimated: int
    source: Literal["git_object", "generated"] = "git_object"


class ExclusionRecord(BaseModel):
    path: str
    reason: str
    kind: Literal["policy", "binary", "denied", "unreadable"] = "policy"


class ScopeInfo(BaseModel):
    mode: ScopeMode
    commit: str | None = None
    base: str | None = None
    head_sha: str
    review_rev: str
    diff_range: str
    worktree_dirty: bool
    dirty_paths: int
    changed_files: int
    reviewed_files: int
    snapshot_source: Literal["git_objects"] = "git_objects"


class PrivacyInfo(BaseModel):
    external_content: bool
    authorization: str | None = None
    granted: bool
    provider: str | None = None
    model: str | None = None
    endpoint_host: str | None = None
    notes: list[str] = Field(default_factory=list)


class BudgetInfo(BaseModel):
    hard_limit: int
    safety_margin: int
    system_reserve: int
    instruction_reserve: int
    output_reserve: int
    file_budget: int
    diff_tokens: int = 0
    file_tokens: int = 0
    task_prompt_tokens: int = 0
    estimated_input_tokens: int = 0
    estimated_total_tokens: int = 0
    warning: bool = False
    blocked: bool = False
    blocked_reason: str | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    output_over_reserve: bool = False
    violation: bool = False
    estimate_note: str = (
        "estimate_text_tokens is an approximation (CJK-aware); actual usage is "
        "read from turn.completed and never assumed."
    )


class ExecutionInfo(BaseModel):
    executable: str | None = None
    argv: list[str] = Field(default_factory=list)
    sandbox: str = "read-only"
    isolation: str = "isolated"
    timeout_s: int = 600
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    timed_out: bool = False
    launcher_error: str | None = None
    stderr_tail: str = ""
    stdout_bytes: int = 0
    thread_id: str | None = None
    noise_filtered: int = 0
    errors: list[str] = Field(default_factory=list)
    snapshot_intact: bool | None = None


class Manifest(BaseModel):
    schema_version: str = SCHEMA_VERSION
    review_id: str
    review_type: ReviewType
    created_at: str
    workspace: str
    scope: ScopeInfo | None = None
    files: list[FileRecord] = Field(default_factory=list)
    exclusions: list[ExclusionRecord] = Field(default_factory=list)
    privacy: PrivacyInfo | None = None
    budget: BudgetInfo | None = None
    execution: ExecutionInfo = Field(default_factory=ExecutionInfo)
    execution_status: ExecutionStatus = ExecutionStatus.not_run
    review_status: ReviewStatus = ReviewStatus.not_run
    flags: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    findings_count: int | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    production_effect: Literal["none"] = "none"
