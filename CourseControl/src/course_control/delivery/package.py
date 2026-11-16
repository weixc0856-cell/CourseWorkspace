"""Standard delivery package for a lesson.

The package is deliberately a *copy* layer: it never renders, mixes or
transcodes. It collects the artifacts that already passed the build, records
their SHA-256, and fails when a required artifact is missing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from course_control.rendering.assets import collect_referenced_assets, safe_bundle_name
from course_control.content.paths import LessonPaths, is_under
from course_control.platform.utils import probe_media

REQUIRED = "required"
OPTIONAL = "optional"


class PackageError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(root: Path, path: Path, required: bool, status: str | None = None) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "required": required,
        "status": status or ("present" if path.is_file() else "missing"),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": _sha(path) if path.is_file() else None,
    }


def _copy(root: Path, source: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _final_video(paths: LessonPaths) -> Path:
    mixed = paths.build_root / "final" / "course-video-mixed.mp4"
    clean = paths.build_root / "final" / "course-video.mp4"
    if mixed.is_file():
        return mixed
    return clean


def _subtitles(paths: LessonPaths) -> list[Path]:
    files: list[Path] = []
    accepted = paths.subtitles_path()
    if accepted is not None and accepted.is_file():
        files.append(accepted)
    for suffix in (".srt", ".ass", ".vtt"):
        candidate = paths.build_root / "subtitles" / f"bilingual.draft{suffix}"
        if candidate.is_file():
            files.append(candidate)
        generated = paths.build_root / f"subtitles{suffix}"
        if generated.is_file():
            files.append(generated)
    # Keep the first file per suffix; accepted lesson subtitles win.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in files:
        if path.suffix.lower() in seen:
            continue
        seen.add(path.suffix.lower())
        unique.append(path)
    return unique



QUALITY_IDS = {"Q1", "Q2", "Q3", "Q4", "Q5"}
_BAD_DIMENSIONS = {"BLOCKED", "INCOMPLETE", "FAIL"}


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _quality_problems(certificate_path: Path, quality_path: Path, lesson: str) -> list[str]:
    """Check the typed certificate and the quality report it pins."""
    problems: list[str] = []
    from course_control.quality.certificate import load as load_certificate

    try:
        certificate = load_certificate(certificate_path)
    except Exception:  # noqa: BLE001 - an invalid certificate is a problem
        certificate = None
    if certificate is None:
        problems.append("quality certificate missing or invalid")
    else:
        if certificate.project_id != lesson:
            problems.append(
                f"certificate is for {certificate.project_id}, not {lesson}"
            )
        if certificate.verdict != "pass":
            problems.append(f"quality certificate is {certificate.verdict}")
        if not certificate.quality_report_sha256:
            problems.append("certificate does not pin the quality report")
        elif not quality_path.is_file() or certificate.quality_report_sha256 != _sha(quality_path):
            problems.append("certificate is stale (quality report changed)")

    quality = _read_json(quality_path)
    if quality is None:
        problems.append("quality report missing or invalid")
        return problems
    states = quality.get("states") or {}
    if not states.get("VERIFY_PASS"):
        problems.append("quality report is not VERIFY_PASS")
    if states.get("VERIFY_INCOMPLETE") or states.get("VERIFY_FAIL"):
        problems.append("quality report contains an incomplete or failed verification")
    if states.get("BLOCKED_WARNINGS"):
        problems.append("quality report has blocking warnings")
    if not states.get("RELEASE_APPROVED"):
        problems.append("quality report has no release approval")
    dimensions = {
        str(item.get("id")): str(item.get("status"))
        for item in quality.get("dimensions") or []
        if isinstance(item, dict)
    }
    missing = sorted(QUALITY_IDS - set(dimensions))
    if missing:
        problems.append("quality report is missing dimensions: " + ", ".join(missing))
    bad = sorted(key for key, status in dimensions.items() if status in _BAD_DIMENSIONS)
    if bad:
        problems.append("quality dimensions not passed: " + ", ".join(bad))
    return problems


def _approval_problems(
    review_path: Path,
    release_path: Path,
    build_report: Path,
    final_video: Path,
    quality_path: Path,
) -> list[str]:
    """Check that both approvals bind this build, film and quality report."""
    problems: list[str] = []
    expected = {
        "build_report_sha256": _sha(build_report) if build_report.is_file() else None,
        "final_video_sha256": _sha(final_video) if final_video.is_file() else None,
        "quality_report_sha256": _sha(quality_path) if quality_path.is_file() else None,
    }
    for label, path in (("review", review_path), ("release", release_path)):
        approval = _read_json(path)
        if approval is None:
            problems.append(f"{label} approval missing or invalid")
            continue
        if approval.get("decision") != "approved" or not str(approval.get("approved_by") or "").strip():
            problems.append(f"{label} approval is not a named approval")
        for key, value in expected.items():
            if value is None:
                problems.append(f"{label} approval cannot be checked: {key.replace('_sha256', '')} missing")
            elif approval.get(key) != value:
                problems.append(f"{label} approval does not bind the current {key.replace('_sha256', '')}")
    return problems


def _delivery_verdict(paths: LessonPaths) -> tuple[str, list[str], dict]:
    """The package verdict must describe the evidence, not hope.

    A package is a copy of the build, so it can be produced at any time.  Its
    verdict is ``pass`` only when the typed certificate, all five quality
    dimensions, both approvals (bound to this build, film and report) and the
    storyboard sign-off agree.  Any missing piece is ``incomplete``.
    """
    build_root = paths.build_root
    reasons: list[str] = []
    detail: dict = {}

    certificate_path = build_root / "quality" / "certificate.json"
    quality_path = build_root / "quality" / "quality-report.json"
    build_report = build_root / "final" / "build-report.json"
    final = _final_video(paths)
    detail["certificate"] = str(certificate_path) if certificate_path.is_file() else None
    detail["quality_report"] = str(quality_path) if quality_path.is_file() else None

    reasons.extend(_quality_problems(certificate_path, quality_path, paths.slug))
    reasons.extend(
        _approval_problems(
            build_root / "quality" / "review-approval.json",
            build_root / "quality" / "release-approval.json",
            build_report,
            final,
            quality_path,
        )
    )

    try:
        from course_control.release.check import content_exception_for

        exception = content_exception_for(build_root, paths.slug)
        if exception is not None:
            reasons.append(
                "open content exception: "
                + str(exception.get("reason") or exception.get("detail") or "see queue")
            )
    except Exception:  # noqa: BLE001 - the verdict records missing evidence
        reasons.append("content exception queue could not be read")

    try:
        from course_control.authoring.pipeline import assert_storyboard_signed

        assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
        detail["storyboard_signed"] = True
    except Exception as exc:  # noqa: BLE001 - the verdict records the reason
        detail["storyboard_signed"] = False
        reasons.append(str(exc))

    certificate = _read_json(certificate_path)
    if str((certificate or {}).get("verdict") or "") == "fail":
        return "fail", reasons, detail
    return ("pass" if not reasons else "incomplete"), reasons, detail


def build_package(paths: LessonPaths, output_root: Path | None = None) -> tuple[dict, Path]:
    """Collect a delivery package and return (manifest, package_root).

    Raises ``PackageError`` when a required artifact is missing or unreadable.
    Optional artifacts are recorded as ``not_applicable`` instead of being
    invented.
    """
    build_root = paths.build_root
    final_root = (output_root or paths.delivery_root).resolve()
    # Delivery lives in the content root, next to build/, not in the repository;
    # accept either root so a content-root delivery is not rejected.
    allowed = [paths.workspace]
    if paths.content_base is not None:
        allowed.append(paths.content_base)
    if not any(is_under(base, final_root) for base in allowed):
        raise PackageError(f"package output must stay inside the workspace: {final_root}")
    # Build beside the target and swap only after the new package is complete.
    # A failed run must never destroy the last valid delivery package.
    root = final_root.with_name(final_root.name + ".tmp")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    build_report = build_root / "final" / "build-report.json"
    media_qc = build_root / "quality" / "media-qc.json"
    # The resequenced meta is the measured clock the film and SRT were built
    # from; the per-slide meta is the pre-resequencing source and only stands
    # in when no resequenced track exists.
    narration_meta = build_root / "narration" / "narration.resequenced.meta.json"
    if not narration_meta.is_file():
        narration_meta = build_root / "narration" / "narration.meta.json"
    final = _final_video(paths)

    required: list[tuple[str, Path, Path | None]] = [
        ("final/master.mp4", final, final),
        ("build-report.json", build_report, build_report),
        ("evidence/media-qc.json", media_qc, media_qc),
    ]
    if paths.lesson.narration.enabled:
        required.append((narration_meta.name, narration_meta, narration_meta))

    missing: list[str] = []
    for relative, source, _ in required:
        if not source.is_file():
            missing.append(relative)
    if missing:
        raise PackageError("missing required artifacts: " + ", ".join(missing))

    # A master that cannot be probed is not a deliverable.
    try:
        probe = probe_media(final).as_dict()
    except Exception as exc:  # noqa: BLE001
        raise PackageError(f"final video is not readable: {exc}") from exc

    records: list[dict] = []
    for relative, source, _ in required:
        target = _copy(root, source, relative)
        records.append(_record(root, target, True))

    # The package must carry the evidence a verifier needs: a typed
    # certificate, the quality report it pins, both approvals and the
    # storyboard sign-off.  A pass package without them cannot be verified.
    evidence_pairs = [
        ("evidence/certificate.json", build_root / "quality" / "certificate.json"),
        ("evidence/quality-report.json", build_root / "quality" / "quality-report.json"),
        ("evidence/review-approval.json", build_root / "quality" / "review-approval.json"),
        ("evidence/release-approval.json", build_root / "quality" / "release-approval.json"),
    ]
    for relative, source in evidence_pairs:
        if source.is_file():
            records.append(_record(root, _copy(root, source, relative), True))
        else:
            records.append({"path": relative, "required": True, "status": "missing", "bytes": None, "sha256": None})
    storyboard_pairs = [
        ("evidence/storyboard/review.json", paths.lesson_dir / "authoring" / "storyboard-review.json"),
        ("evidence/storyboard/review.html", paths.lesson_dir / "authoring" / "storyboard-review.html"),
        ("evidence/storyboard/decisions.json", paths.lesson_dir / "authoring" / "storyboard-decisions.json"),
    ]
    storyboard_evidence = all(source.is_file() for _, source in storyboard_pairs)
    for relative, source in storyboard_pairs:
        if source.is_file():
            records.append(_record(root, _copy(root, source, relative), True))
        else:
            records.append({"path": relative, "required": True, "status": "missing", "bytes": None, "sha256": None})

    captioned = build_root / "final" / "course-video-captioned.mp4"
    if captioned.is_file():
        records.append(_record(root, _copy(root, captioned, "final/captioned.mp4"), False))
    else:
        records.append({"path": "final/captioned.mp4", "required": False, "status": "not_applicable"})

    subtitles = _subtitles(paths) if paths.lesson.subtitles.enabled else []
    if paths.lesson.subtitles.enabled and not subtitles:
        missing.append("subtitles")
    for source in subtitles:
        records.append(_record(root, _copy(root, source, f"final/subtitles{source.suffix}"), True))

    review = build_root / "review" / "review.json"
    if review.is_file():
        records.append(_record(root, _copy(root, review, "review/review.json"), False))
    else:
        records.append({"path": "review/review.json", "required": False, "status": "not_applicable"})

    decisions = build_root / "review" / "decisions.json"
    if decisions.is_file():
        records.append(_record(root, _copy(root, decisions, "review/decisions.json"), False))
    else:
        records.append({"path": "review/decisions.json", "required": False, "status": "not_applicable"})

    logs = build_root / "logs"
    if logs.is_dir():
        for source in sorted(logs.glob("*.log")):
            records.append(_record(root, _copy(root, source, f"logs/{source.name}"), False))

    # External assets (BGM bed, voice reference) are part of reproducibility.
    # Bundle them so the package does not depend on this machine's libraries.
    external_assets: list[dict] = []
    referenced_assets = collect_referenced_assets(paths.workspace, build_root)
    for asset in referenced_assets:
        if asset["origin"] not in {"external", "voice-ref"}:
            # Configured roots are recorded but not copied: the mixed master
            # already carries the audio, and the source stays in its library.
            continue
        source = Path(asset["path"])
        if not source.is_file():
            missing.append(f"external asset: {asset['asset_id']}")
            continue
        name = safe_bundle_name(asset)
        target = _copy(root, source, f"assets/external/{name}")
        bundled = {
            "asset_id": asset["asset_id"],
            "source_path": asset["path"],
            "origin": asset["origin"],
            "license_status": asset.get("license_status"),
            "attribution": asset.get("attribution"),
            "bundled_path": f"assets/external/{name}",
            "sha256": _sha(target),
            "bytes": target.stat().st_size,
        }
        external_assets.append(bundled)

    if missing:
        raise PackageError("missing required artifacts: " + ", ".join(sorted(set(missing))))

    run_id = ""
    try:
        run_id = str(json.loads(build_report.read_text(encoding="utf-8")).get("run_id") or "")
    except (OSError, json.JSONDecodeError):
        pass
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-package"
    metadata = {
        "schema_version": 1,
        "lesson": paths.slug,
        "title_en": paths.lesson.title_en,
        "title_zh": paths.lesson.title_zh,
        "run_id": run_id,
        "duration_s": probe.get("duration"),
        "resolution": [probe.get("width"), probe.get("height")],
        "fps": probe.get("fps"),
        "codec": probe.get("codec"),
        "languages": sorted(
            {
                paths.lesson.subtitles.bottom_language,
                *(
                    [paths.lesson.subtitles.top_language]
                    if paths.lesson.subtitles.bilingual
                    else []
                ),
            }
        ),
        "content_kind": paths.lesson.audio.content_kind,
        "generated_at": _now(),
    }
    (root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    records.append(_record(root, root / "metadata.json", True))

    verdict, verdict_reasons, verdict_detail = _delivery_verdict(paths)
    manifest = {
        "schema_version": 1,
        "lesson": paths.slug,
        "run_id": run_id,
        "generated_at": _now(),
        "verdict": verdict,
        "verdict_reasons": verdict_reasons,
        "verdict_detail": verdict_detail,
        "evidence": {"storyboard": storyboard_evidence},
        "files": records,
        "external_assets": external_assets,
        "referenced_assets": referenced_assets,
        "missing": [],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )

    checklist = [
        f"# Delivery checklist — {paths.slug}",
        "",
        f"- run_id: `{run_id or 'unknown'}`",
        f"- generated_at: {manifest['generated_at']}",
        f"- master: `final/master.mp4` ({probe.get('duration')} s, {probe.get('width')}x{probe.get('height')})",
        f"- verdict: `{verdict}`",
        *([f"- reason: {reason}" for reason in verdict_reasons] if verdict_reasons else []),
        "",
        "| file | required | status | sha256 |",
        "| --- | --- | --- | --- |",
    ]
    for item in records:
        checklist.append(
            f"| `{item['path']}` | {'yes' if item['required'] else 'no'} | "
            f"{item['status']} | `{(item.get('sha256') or '')[:16]}` |"
        )
    (root / "delivery-checklist.md").write_text(
        "\n".join(checklist) + "\n", encoding="utf-8"
    )
    if verdict != "pass":
        # An incomplete or failed attempt must never displace the last passing
        # delivery.  Keep it beside the delivery for inspection and say so.
        attempt = final_root.with_name(final_root.name + ".attempt")
        if attempt.exists():
            shutil.rmtree(attempt)
        root.rename(attempt)
        manifest["installed"] = False
        manifest["attempt_path"] = str(attempt)
        (attempt / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
        )
        return manifest, attempt

    backup = final_root.with_name(final_root.name + ".old")
    if backup.exists():
        shutil.rmtree(backup)
    if final_root.exists():
        final_root.rename(backup)
    try:
        root.rename(final_root)
    except Exception:
        if backup.exists() and not final_root.exists():
            backup.rename(final_root)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    manifest["installed"] = True
    (final_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    return manifest, final_root


def _package_path(root: Path, relative: object) -> Path | None:
    """Resolve a manifest path without allowing absolute paths or traversal."""
    value = str(relative or "")
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    target = (root / candidate).resolve()
    if not is_under(root, target):
        return None
    return target


def verify_package(root: Path) -> list[str]:
    """Verify hashes and the evidence chain a pass package claims."""
    root = root.resolve()
    problems: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json is unreadable: {exc}"]

    if int(manifest.get("schema_version") or 0) != 1:
        problems.append("manifest schema_version is not 1")
    lesson = str(manifest.get("lesson") or "")
    if not lesson:
        problems.append("manifest does not name a lesson")
    if manifest.get("verdict") != "pass":
        problems.append(f"manifest verdict is {manifest.get('verdict') or 'missing'}, not pass")

    items = [item for item in manifest.get("files") or [] if isinstance(item, dict)]
    by_path = {str(item.get("path") or ""): item for item in items}
    required = {
        "final/master.mp4",
        "build-report.json",
        "evidence/media-qc.json",
        "evidence/certificate.json",
        "evidence/quality-report.json",
        "evidence/review-approval.json",
        "evidence/release-approval.json",
    }
    if (manifest.get("evidence") or {}).get("storyboard"):
        required.update(
            {
                "evidence/storyboard/review.json",
                "evidence/storyboard/review.html",
                "evidence/storyboard/decisions.json",
            }
        )
    for relative in sorted(required):
        if relative not in by_path:
            problems.append(f"manifest does not list required: {relative}")
        elif by_path[relative].get("status") != "present":
            problems.append(f"manifest says {relative} is not present")

    for item in items:
        relative = str(item.get("path") or "")
        path = _package_path(root, relative)
        if path is None:
            problems.append(f"unsafe package path: {relative}")
            continue
        if item.get("status") != "present":
            if item.get("required"):
                problems.append(f"missing required: {relative}")
            continue
        if not path.is_file():
            problems.append(f"missing: {relative}")
            continue
        if item.get("sha256") and _sha(path) != item["sha256"]:
            problems.append(f"hash mismatch: {relative}")

    for item in manifest.get("external_assets") or []:
        relative = str((item or {}).get("bundled_path") or "")
        path = _package_path(root, relative)
        if path is None:
            problems.append(f"unsafe bundled asset path: {relative or item.get('asset_id')}")
            continue
        if not path.is_file():
            problems.append(f"missing bundled asset: {relative or item.get('asset_id')}")
            continue
        if item.get("sha256") and _sha(path) != item["sha256"]:
            problems.append(f"hash mismatch: {relative}")

    certificate = root / "evidence" / "certificate.json"
    quality = root / "evidence" / "quality-report.json"
    build_report = root / "build-report.json"
    master = root / "final" / "master.mp4"
    if certificate.is_file() or quality.is_file():
        problems.extend(_quality_problems(certificate, quality, lesson))
    else:
        problems.append("evidence certificate and quality report are missing")
    problems.extend(
        _approval_problems(
            root / "evidence" / "review-approval.json",
            root / "evidence" / "release-approval.json",
            build_report,
            master,
            quality,
        )
    )

    if (manifest.get("evidence") or {}).get("storyboard"):
        review = _read_json(root / "evidence" / "storyboard" / "review.json")
        page = root / "evidence" / "storyboard" / "review.html"
        decisions = root / "evidence" / "storyboard" / "decisions.json"
        if review is None:
            problems.append("storyboard review evidence is missing or invalid")
        else:
            if not page.is_file() or review.get("page_sha256") != _sha(page):
                problems.append("storyboard review page is missing or changed")
            if not decisions.is_file() or review.get("decisions_sha256") != _sha(decisions):
                problems.append("storyboard decisions are missing or changed")
    return problems
