from __future__ import annotations

import time

from ..branding import delivery_path, run_branding
from ..contracts import Status
from ..paths import ContractError, LessonPaths
from .base import StageOutcome


def run(paths: LessonPaths, *, force: bool = False) -> StageOutcome:
    """Render the brand segments and stitch the delivery master."""

    started = time.monotonic()
    if not paths.lesson.branding.enabled:
        return StageOutcome(
            "brand", Status.NOT_APPLICABLE, reason="branding_disabled"
        )
    try:
        plan, record = run_branding(paths, force=force)
    except ContractError as exc:
        return StageOutcome(
            "brand",
            Status.FAIL,
            errors=[str(exc)],
            reason="brand_failed",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    return StageOutcome(
        "brand",
        Status.PASS,
        outputs=[delivery_path(paths)],
        warnings=[f"stitch mode: {record['mode']}"],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
