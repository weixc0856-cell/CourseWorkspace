"""Layered quality gates: Hard / Grammar / Metrics / Human.

The universal hard constraints never bend.  Grammar constraints are the
production envelope of a specific visual language and may be waived in writing.
Metrics are reported, never used as a silent pass/fail.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .animation_score import score as motion_score
from .beats import load_segments, load_sheet, validate_sheet_report
from .grammar import try_load_registry


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _status(record: dict) -> str:
    return str(record.get("status") or record.get("verdict") or "").lower()


def hard_checks(paths) -> list[dict]:
    """Collect universal failures already proven by build and media QC."""
    failures: list[dict] = []
    build = _read_json(paths.build_root / "final" / "build-report.json") or {}
    for check in build.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if _status(check) == "fail":
            failures.append(
                {
                    "source": "build-report",
                    "id": check.get("id"),
                    "detail": check.get("detail") or check.get("actual"),
                }
            )
    media = _read_json(paths.build_root / "quality" / "media-qc.json") or {}
    for check in media.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if _status(check) == "fail":
            failures.append(
                {
                    "source": "media-qc",
                    "id": check.get("id"),
                    "detail": check.get("detail") or check.get("actual"),
                }
            )
    return failures


def incomplete_checks(paths) -> list[dict]:
    """Checks that could not run are not passes. They block a release."""
    failures: list[dict] = []
    build = _read_json(paths.build_root / "final" / "build-report.json") or {}
    for check in build.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if _status(check) in {"incomplete", "not_run", "blocked"}:
            failures.append(
                {
                    "source": "build-report",
                    "id": check.get("id"),
                    "detail": check.get("detail") or check.get("actual"),
                }
            )
    media = _read_json(paths.build_root / "quality" / "media-qc.json") or {}
    for check in media.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if _status(check) in {"incomplete", "not_run", "blocked"}:
            failures.append(
                {
                    "source": "media-qc",
                    "id": check.get("id"),
                    "detail": check.get("detail") or check.get("actual"),
                }
            )
    return failures


def grammar_report(paths, registry, profile: str | None = None) -> dict:
    sheet_path = paths.lesson_dir / "authoring" / "beats.yaml"
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not sheet_path.is_file() or not meta_path.is_file():
        return {"errors": [], "warnings": [], "issues": []}
    sheet = load_sheet(sheet_path)
    if profile:
        sheet = sheet.model_copy(update={"grammar": profile})
    segments = load_segments(meta_path)
    return validate_sheet_report(sheet, segments, registry=registry)


def grammar_issues(paths, registry, profile: str | None = None) -> list[str]:
    """Structural grammar errors only; creative thresholds are warnings."""
    return grammar_report(paths, registry, profile)["errors"]


def metrics(paths, registry, profile: str | None = None) -> dict:
    sheet_path = paths.lesson_dir / "authoring" / "beats.yaml"
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not sheet_path.is_file() or not meta_path.is_file():
        return {}
    sheet = load_sheet(sheet_path)
    segments = load_segments(meta_path)
    media = _read_json(paths.build_root / "quality" / "media-qc.json")
    build = _read_json(paths.build_root / "final" / "build-report.json")
    result = motion_score(
        sheet,
        segments,
        media_qc=media,
        build_verdict=(build or {}).get("verdict"),
        registry=registry,
        profile=profile,
    )
    return {
        "score": result.get("score"),
        "components": result.get("components"),
        "metrics": result.get("metrics"),
        "release_gate": result.get("release_gate", "legacy"),
    }


def decide(
    hard: Iterable[dict],
    grammar: Iterable[str],
    waivers: Iterable[str] = (),
    *,
    incomplete: Iterable[dict] = (),
    grammar_warnings: Iterable[str] = (),
) -> dict:
    waived = {item.strip() for item in waivers if item and item.strip()}
    remaining = [issue for issue in grammar if not any(issue.startswith(w) for w in waived)]
    hard_fail = list(hard)
    incomplete_fail = list(incomplete)
    warnings = list(grammar_warnings)
    if hard_fail:
        verification = "fail"
    elif incomplete_fail:
        verification = "incomplete"
    else:
        verification = "pass"
    return {
        "hard_failures": hard_fail,
        "incomplete_failures": incomplete_fail,
        "grammar_failures": remaining,
        "grammar_warnings": warnings,
        "waived": sorted(waived),
        "verification_status": verification,
        "hard_ok": not hard_fail and not incomplete_fail,
        "grammar_ok": not remaining,
        "human_review_required": True,
        "releasable": not hard_fail and not incomplete_fail and not remaining,
        "note": "automatic checks never approve a release; human sign-off is required",
    }


def evaluate(paths, *, profile: str | None = None, waivers: Iterable[str] = ()) -> dict:
    registry = try_load_registry(paths.workspace)
    hard = hard_checks(paths)
    incomplete = incomplete_checks(paths)
    grammar = grammar_report(paths, registry, profile)
    quality = _read_json(paths.build_root / "quality" / "quality-report.json") or {}
    quality_warnings: list[str] = []
    if quality:
        for dimension in quality.get("dimensions") or []:
            status = str(dimension.get("status") or "").upper()
            if status in {"INCOMPLETE", "BLOCKED", "FAIL"}:
                incomplete.append(
                    {
                        "source": "quality-report",
                        "id": dimension.get("id"),
                        "detail": dimension.get("reason"),
                    }
                )
            elif status == "WARN":
                quality_warnings.append(
                    f"{dimension.get('id')} {dimension.get('name')}: {dimension.get('reason')}"
                )
    else:
        incomplete.append(
            {
                "source": "quality-report",
                "id": "Q0",
                "detail": "quality-report.json missing; run quality-report first",
            }
        )
    warnings = grammar["warnings"] + quality_warnings
    report = {
        "schema_version": 1,
        "lesson": paths.slug,
        "profile": profile,
        "hard": hard,
        "incomplete": incomplete,
        "grammar": grammar["errors"],
        "grammar_warnings": grammar["warnings"],
        "quality_warnings": quality_warnings,
        "metrics": metrics(paths, registry, profile),
        **decide(
            hard,
            grammar["errors"],
            waivers,
            incomplete=incomplete,
            grammar_warnings=warnings,
        ),
    }
    target = paths.build_root / "quality" / "gate.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["decide", "evaluate", "grammar_issues", "grammar_report", "hard_checks", "incomplete_checks", "metrics"]
