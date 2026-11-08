"""Independent, read-only second-opinion review runner.

The runner never participates in the production chain: it does not change
lessons, does not modify source files, and never emits a production verdict.
It produces a local audit trail under ``build/reviews/`` whose status is split
into two independent axes (execution and review completeness).
"""

from __future__ import annotations

from .schema import (
    PRODUCTION_EFFECT,
    SCHEMA_VERSION,
    ExecutionStatus,
    Finding,
    FindingsEnvelope,
    ReviewStatus,
    ReviewType,
    ScopeMode,
    Severity,
)

__all__ = [
    "PRODUCTION_EFFECT",
    "SCHEMA_VERSION",
    "ExecutionStatus",
    "Finding",
    "FindingsEnvelope",
    "ReviewStatus",
    "ReviewType",
    "ScopeMode",
    "Severity",
]
