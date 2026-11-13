"""Layered quality gates: Hard / Grammar / Metrics / Human.

The universal hard constraints never bend.  Grammar constraints are the
production envelope of a specific visual language and may be waived in writing.
Metrics are reported, never used as a silent pass/fail.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from course_control.direction.animation_score import score as motion_score
from course_control.direction.beats import load_segments, load_sheet, validate_sheet_report
from course_control.rendering.grammar import try_load_registry


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


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _newer(report: Path, artifact: Path, slack: float = 1.0) -> bool:
    """True when the artifact was written after the report that describes it."""
    try:
        return report.stat().st_mtime + slack < artifact.stat().st_mtime
    except OSError:
        return False


def freshness_problems(build_root: Path) -> list[dict]:
    """Reports that no longer describe the current artifacts are not evidence.

    The build report records the hash of every delivered artifact; a changed
    final file makes it stale.  The other reports do not carry input hashes
    yet, so they fall back to a modification-time comparison.  A stale report
    becomes an ``incomplete`` check, never a silent pass (P5 lesson 2).
    """
    problems: list[dict] = []
    build_path = build_root / "final" / "build-report.json"
    build = _read_json(build_path)
    if build:
        for artifact in build.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            relative = str(artifact.get("path") or "")
            digest = artifact.get("sha256")
            if not relative or not digest or not relative.startswith("final/"):
                continue
            target = build_root / relative
            if not target.is_file():
                problems.append(
                    {
                        "source": "build-report",
                        "id": "freshness.build",
                        "detail": f"artifact missing: {relative}",
                    }
                )
                break
            if _sha256(target) != digest:
                problems.append(
                    {
                        "source": "build-report",
                        "id": "freshness.build",
                        "detail": f"artifact changed since build-report: {relative}",
                    }
                )
                break

    media_report = build_root / "quality" / "media-qc.json"
    media = _read_json(media_report)
    if media and media.get("video"):
        video = Path(str(media["video"]))
        if video.is_file() and _newer(media_report, video):
            problems.append(
                {
                    "source": "media-qc",
                    "id": "freshness.media",
                    "detail": "final video is newer than media-qc.json",
                }
            )

    subtitles_report = build_root / "quality" / "subtitles-qc.json"
    subtitles = _read_json(subtitles_report)
    if subtitles:
        source = subtitles.get("source") or {}
        target = source.get("path")
        if target:
            path = Path(str(target))
            if not path.is_file():
                problems.append(
                    {
                        "source": "subtitles-qc",
                        "id": "freshness.subtitles",
                        "detail": "audited subtitle file is missing",
                    }
                )
            elif source.get("sha256"):
                if _sha256(path) != source.get("sha256"):
                    problems.append(
                        {
                            "source": "subtitles-qc",
                            "id": "freshness.subtitles",
                            "detail": "subtitle file changed since subtitles-qc",
                        }
                    )
            elif _newer(subtitles_report, path):
                problems.append(
                    {
                        "source": "subtitles-qc",
                        "id": "freshness.subtitles",
                        "detail": "subtitle file is newer than subtitles-qc.json",
                    }
                )

    quality_report = build_root / "quality" / "quality-report.json"
    if _read_json(quality_report):
        # The quality report reads the build and media reports; subtitle QC is
        # gated separately, so a newer subtitle report does not stale it.
        for dependency in (build_path, media_report):
            if dependency.is_file() and _newer(quality_report, dependency):
                problems.append(
                    {
                        "source": "quality-report",
                        "id": "freshness.quality",
                        "detail": f"{dependency.name} is newer than quality-report.json",
                    }
                )
                break
    return problems


def subtitles_qc_result(paths) -> tuple[list[dict], list[dict]]:
    """Subtitle QC is a delivery gate, not a postscript (P5 lesson 1)."""
    lesson = getattr(paths, "lesson", None)
    subtitles = getattr(lesson, "subtitles", None)
    if subtitles is not None and not getattr(subtitles, "enabled", False):
        return [], []
    report = _read_json(paths.build_root / "quality" / "subtitles-qc.json")
    if report is None:
        return [], [
            {
                "source": "subtitles-qc",
                "id": "subtitles.qc",
                "detail": "no subtitle QC report; run subtitles-qc after subtitles-build",
            }
        ]
    status = str(report.get("status") or "").upper()
    if status == "FAIL":
        detail = "; ".join((report.get("errors") or [])[:3]) or "subtitle QC failed"
        return [{"source": "subtitles-qc", "id": "subtitles.qc", "detail": detail}], []
    if status not in {"PASS", "WARN"}:
        return [], [
            {
                "source": "subtitles-qc",
                "id": "subtitles.qc",
                "detail": f"subtitle QC status is {status or 'unknown'}",
            }
        ]
    return [], []


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
    blocking_warnings: Iterable[str] = (),
    human_review_items: Iterable[str] = (),
) -> dict:
    waived = {item.strip() for item in waivers if item and item.strip()}
    remaining = [issue for issue in grammar if not any(issue.startswith(w) for w in waived)]
    hard_fail = list(hard)
    incomplete_fail = list(incomplete)
    warnings = list(grammar_warnings)
    blocking = list(blocking_warnings)
    human = list(human_review_items)
    if hard_fail:
        verification = "fail"
    elif incomplete_fail or blocking:
        verification = "incomplete"
    else:
        verification = "pass"
    return {
        "hard_failures": hard_fail,
        "incomplete_failures": incomplete_fail,
        "grammar_failures": remaining,
        "grammar_warnings": warnings,
        "blocking_warnings": blocking,
        "human_review_items": human,
        "waived": sorted(waived),
        "verification_status": verification,
        "hard_ok": not hard_fail and not incomplete_fail,
        "grammar_ok": not remaining,
        "human_review_required": True,
        "needs_human_review": bool(human),
        "releasable": not hard_fail and not incomplete_fail and not remaining and not blocking,
        "note": "automatic checks never approve a release; human sign-off is required",
    }


def evaluate(paths, *, profile: str | None = None, waivers: Iterable[str] = ()) -> dict:
    registry = try_load_registry(paths.workspace)
    hard = hard_checks(paths)
    incomplete = incomplete_checks(paths)
    subtitle_fail, subtitle_incomplete = subtitles_qc_result(paths)
    hard.extend(subtitle_fail)
    incomplete.extend(subtitle_incomplete)
    freshness = freshness_problems(paths.build_root)
    incomplete.extend(freshness)
    grammar = grammar_report(paths, registry, profile)
    quality = _read_json(paths.build_root / "quality" / "quality-report.json") or {}
    quality_warnings: list[str] = []
    blocking_warnings: list[str] = []
    human_review_items: list[str] = []
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
                message = (
                    f"{dimension.get('id')} {dimension.get('name')}: {dimension.get('reason')}"
                )
                quality_warnings.append(message)
                if dimension.get("warning_class") == "blocking":
                    blocking_warnings.append(message)
                else:
                    human_review_items.append(message)
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
        "blocking_warnings": blocking_warnings,
        "human_review_items": human_review_items,
        "freshness": freshness,
        "metrics": metrics(paths, registry, profile),
        **decide(
            hard,
            grammar["errors"],
            waivers,
            incomplete=incomplete,
            grammar_warnings=warnings,
            blocking_warnings=blocking_warnings,
            human_review_items=human_review_items,
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
