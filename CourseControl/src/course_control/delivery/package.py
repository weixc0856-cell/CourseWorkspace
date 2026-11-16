"""Standard delivery package for a lesson.

The package is deliberately a *copy* layer: it never renders, mixes or
transcodes. It collects the artifacts that already passed the build, records
their SHA-256, and fails when a required artifact is missing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from course_control.rendering.assets import collect_referenced_assets, safe_bundle_name
from course_control.content.paths import LessonPaths
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
    if _is_link(source):
        raise PackageError(f"refusing to copy a link outside the build: {source}")
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



SCHEMA_VERSION = 2
BASE_REQUIRED = {
    "final/master.mp4",
    "build-report.json",
    "evidence/media-qc.json",
    "evidence/certificate.json",
    "evidence/quality-report.json",
    "evidence/review-approval.json",
    "evidence/release-approval.json",
    "metadata.json",
    "delivery-checklist.md",
}
STORYBOARD_EVIDENCE = (
    "evidence/storyboard/review.json",
    "evidence/storyboard/review.html",
    "evidence/storyboard/decisions.json",
)
SHA_RE = re.compile(r"[0-9a-f]{64}")


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    checker = getattr(path, "is_junction", None)
    if callable(checker):
        try:
            return bool(checker())
        except OSError:
            return False
    return False


def _link_ancestor(root: Path, path: Path) -> Path | None:
    """The first ancestor of path, below root, that is a link."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and _is_link(current):
            return current
    return None


def _real_file(root: Path, path: Path) -> bool:
    return (
        path.is_file()
        and not _is_link(path)
        and _link_ancestor(root, path) is None
    )


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def _quality_problems(quality_path: Path, lesson: str) -> list[str]:
    from course_control.quality.evidence import BAD_STATES, normalize_dimensions

    quality = _read_json(quality_path)
    if quality is None:
        return ["quality report missing or invalid"]
    problems: list[str] = []
    version = quality.get("schema_version")
    if type(version) is not int or version != 2:
        problems.append(
            f"quality report schema_version is {version!r}, not 2; "
            "re-run quality-report"
        )
    statuses, status_problems = normalize_dimensions(quality)
    problems.extend(status_problems)
    bad = sorted(
        qid for qid, status in statuses.items() if status in BAD_STATES
    )
    if bad:
        problems.append("quality dimensions not passed: " + ", ".join(bad))
    states = quality.get("states") or {}
    if not states.get("VERIFY_PASS"):
        problems.append("quality report is not VERIFY_PASS")
    if states.get("VERIFY_INCOMPLETE") or states.get("VERIFY_FAIL"):
        problems.append("quality report contains an incomplete or failed verification")
    if states.get("BLOCKED_WARNINGS"):
        problems.append("quality report has blocking warnings")
    return problems


def _certificate_problems(
    certificate_path: Path, quality_path: Path, lesson: str
) -> list[str]:
    from course_control.quality.certificate import load as load_certificate
    from course_control.quality.evidence import quality_content_sha256

    problems: list[str] = []
    raw = _read_json(certificate_path)
    if raw is None:
        return ["quality certificate missing or invalid"]
    version = raw.get("schema_version")
    if type(version) is not int or version != 2:
        return [
            f"quality certificate schema {version!r} is historical; "
            "re-run quality-certificate"
        ]
    try:
        certificate = load_certificate(certificate_path)
    except Exception:  # noqa: BLE001 - an invalid certificate is a problem
        certificate = None
    if certificate is None:
        return ["quality certificate missing or invalid"]
    if certificate.project_id != lesson:
        problems.append(f"certificate is for {certificate.project_id}, not {lesson}")
    if certificate.verdict != "pass":
        problems.append(f"quality certificate is {certificate.verdict}")
    quality = _read_json(quality_path)
    if quality is None:
        problems.append("quality report missing or invalid")
    elif certificate.quality_report_content_sha256 != quality_content_sha256(quality):
        problems.append("certificate does not pin the current quality content")
    return problems


def _delivery_verdict(paths: LessonPaths) -> tuple[str, list[str], dict]:
    """The package verdict must describe the evidence, not hope.

    A package is a copy of the build, so it can be produced at any time.  Its
    verdict is ``pass`` only when the typed certificate, the closed Q1-Q5
    vocabulary, both named approvals (bound to this build, film and report),
    the storyboard sign-off and the content-exception queue agree.
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

    reasons.extend(_certificate_problems(certificate_path, quality_path, paths.slug))
    reasons.extend(_quality_problems(quality_path, paths.slug))

    from course_control.quality.evidence import evidence_problems

    reasons.extend(
        evidence_problems(
            lesson=paths.slug,
            review_path=build_root / "quality" / "review-approval.json",
            release_path=build_root / "quality" / "release-approval.json",
            build_report=build_report,
            final_video=final,
            quality_report=quality_path,
            require_release=True,
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

    storyboard_required = paths.storyboard_source is not None
    detail["storyboard_required"] = storyboard_required
    if storyboard_required:
        try:
            from course_control.authoring.pipeline import assert_storyboard_signed

            assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
            detail["storyboard_signed"] = True
        except Exception as exc:  # noqa: BLE001 - the verdict records the reason
            detail["storyboard_signed"] = False
            reasons.append(str(exc))
        for relative in (
            "authoring/storyboard-review.json",
            "authoring/storyboard-review.html",
            "authoring/storyboard-decisions.json",
        ):
            if not (paths.lesson_dir / relative).is_file():
                reasons.append(f"storyboard evidence missing: {relative}")

    certificate = _read_json(certificate_path)
    if str((certificate or {}).get("verdict") or "") == "fail":
        return "fail", reasons, detail
    return ("pass" if not reasons else "incomplete"), reasons, detail


def build_package(paths: LessonPaths) -> tuple[dict, Path]:
    """Collect a delivery package and return (manifest, package_root).

    Raises ``PackageError`` when a required artifact is missing or unreadable.
    Optional artifacts are recorded as ``not_applicable`` instead of being
    invented.
    """
    build_root = paths.build_root
    # There is exactly one delivery location: <content_root>/deliver/<slug>.
    # An arbitrary output path could rename and delete an unrelated directory.
    final_root = Path(paths.delivery_root)
    if _is_link(final_root):
        raise PackageError(
            f"package output is a link; refusing to write through it: {final_root}"
        )
    # Build beside the target and swap only after the new package is complete.
    # A failed run must never destroy the last valid delivery package.
    root = final_root.with_name(final_root.name + ".tmp")
    if _is_link(root):
        raise PackageError(
            f"package scratch path is a link; refusing to write through it: {root}"
        )
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
        if not source.is_file() or _is_link(source):
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
    storyboard_required = paths.storyboard_source is not None
    storyboard_evidence = storyboard_required and all(
        source.is_file() for _, source in storyboard_pairs
    )
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
        "schema_version": 2,
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
        "schema_version": 2,
        "lesson": paths.slug,
        "run_id": run_id,
        "generated_at": _now(),
        "verdict": verdict,
        "verdict_reasons": verdict_reasons,
        "verdict_detail": verdict_detail,
        "evidence": {
            "storyboard": storyboard_evidence,
            "storyboard_required": storyboard_required,
        },
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
    records.append(_record(root, root / "delivery-checklist.md", True))
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    if verdict != "pass":
        # An incomplete or failed attempt must never displace the last passing
        # delivery.  Keep it beside the delivery for inspection and say so.
        attempt = final_root.with_name(final_root.name + ".attempt")
        if _is_link(attempt):
            raise PackageError(f"attempt path is a link; refusing to write: {attempt}")
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
    if _is_link(backup):
        raise PackageError(f"backup path is a link; refusing to write: {backup}")
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
    """Resolve a manifest path lexically; no link may sit anywhere on it."""
    value = str(relative or "")
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    base = Path(os.path.normpath(root))
    target = Path(os.path.normpath(root / candidate))
    if target == base or base not in target.parents:
        return None
    if _link_ancestor(base, target) is not None:
        return None
    return target


def verify_package(root: Path) -> list[str]:
    """Recompute the evidence a pass package claims; never trust its manifest."""
    raw = Path(root)
    if _is_link(raw):
        return ["package root is a link and was not followed"]
    root = raw.resolve()
    problems: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    manifest = _read_json(manifest_path)
    if manifest is None:
        return ["manifest.json is unreadable"]

    version = manifest.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        hint = (
            "; schema 1 is a historical package, repackage it before verification"
            if version == 1
            else ""
        )
        problems.append(
            f"manifest schema_version is {version!r}, not the integer {SCHEMA_VERSION}{hint}"
        )
    lesson = str(manifest.get("lesson") or "")
    if not lesson:
        problems.append("manifest does not name a lesson")
    if manifest.get("verdict") != "pass":
        problems.append(
            f"manifest verdict is {manifest.get('verdict') or 'missing'}, not pass"
        )

    items = [item for item in manifest.get("files") or [] if isinstance(item, dict)]
    by_path: dict[str, dict] = {}
    for item in items:
        relative = str(item.get("path") or "")
        if relative in by_path:
            problems.append(f"manifest lists {relative} more than once")
            continue
        by_path[relative] = item

    evidence = manifest.get("evidence") or {}
    declared_storyboard = evidence.get("storyboard_required")
    if not isinstance(declared_storyboard, bool):
        problems.append("manifest evidence.storyboard_required is not a boolean")
    # The manifest is not trusted for this: the quality report's Q5 artifact
    # fact is part of the content hash the approvals bind.  If it is absent or
    # unreadable, require the storyboard evidence (fail closed).
    quality_path = root / "evidence" / "quality-report.json"
    quality = _read_json(quality_path)
    storyboard_required = True
    if quality is not None:
        dimensions = {
            str(item.get("id")): item
            for item in quality.get("dimensions") or []
            if isinstance(item, dict)
        }
        artifacts = (dimensions.get("Q5") or {}).get("artifacts") or {}
        signoff = artifacts.get("storyboard_signoff")
        if isinstance(signoff, bool):
            storyboard_required = signoff
    if isinstance(declared_storyboard, bool) and declared_storyboard != storyboard_required:
        problems.append(
            "manifest storyboard_required disagrees with the quality report"
        )
    required = set(BASE_REQUIRED)
    if storyboard_required:
        required.update(STORYBOARD_EVIDENCE)
    for relative in sorted(required):
        item = by_path.get(relative)
        if item is None:
            problems.append(f"manifest does not list required: {relative}")
        elif item.get("status") != "present":
            problems.append(f"manifest says {relative} is not present")
        elif not _valid_sha(item.get("sha256")):
            problems.append(f"manifest entry for {relative} has no sha256")

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
        if not _real_file(root, path):
            problems.append(f"missing or linked package file: {relative}")
            continue
        if not _valid_sha(item.get("sha256")):
            problems.append(f"manifest entry for {relative} has no sha256")
        elif _sha(path) != item.get("sha256"):
            problems.append(f"hash mismatch: {relative}")

    for item in manifest.get("external_assets") or []:
        if not isinstance(item, dict):
            problems.append("external asset entry is not an object")
            continue
        relative = str(item.get("bundled_path") or "")
        path = _package_path(root, relative)
        if path is None:
            problems.append(f"unsafe bundled asset path: {relative or item.get('asset_id')}")
            continue
        if not _real_file(root, path):
            problems.append(f"missing or linked bundled asset: {relative or item.get('asset_id')}")
            continue
        if not _valid_sha(item.get("sha256")):
            problems.append(f"bundled asset has no sha256: {relative}")
        elif _sha(path) != item.get("sha256"):
            problems.append(f"hash mismatch: {relative}")

    certificate_path = root / "evidence" / "certificate.json"
    build_report = root / "build-report.json"
    master = root / "final" / "master.mp4"

    from course_control.quality.evidence import evidence_problems

    problems.extend(_quality_problems(quality_path, lesson))
    problems.extend(_certificate_problems(certificate_path, quality_path, lesson))
    problems.extend(
        evidence_problems(
            lesson=lesson,
            review_path=root / "evidence" / "review-approval.json",
            release_path=root / "evidence" / "release-approval.json",
            build_report=build_report,
            final_video=master,
            quality_report=quality_path,
            require_release=True,
        )
    )

    if storyboard_required:
        from course_control.quality.evidence import is_named_approver

        review = _read_json(root / "evidence" / "storyboard" / "review.json")
        decisions_path = root / "evidence" / "storyboard" / "decisions.json"
        page = root / "evidence" / "storyboard" / "review.html"
        decisions_data = _read_json(decisions_path)
        if review is None:
            problems.append("storyboard review evidence is missing or invalid")
        elif decisions_data is None:
            problems.append("storyboard decisions are missing or invalid")
        else:
            if str(review.get("lesson") or "") != lesson:
                problems.append("storyboard review is for another lesson")
            if not is_named_approver(review.get("approved_by")):
                problems.append("storyboard review was not signed by a named person")
            if str(decisions_data.get("lesson") or "") != lesson:
                problems.append("storyboard decisions are for another lesson")
            if not is_named_approver(decisions_data.get("reviewed_by")):
                problems.append("storyboard decisions were not reviewed by a named person")
            if decisions_data.get("storyboard_sha256") != review.get("storyboard_sha256"):
                problems.append("storyboard decisions were made against another storyboard")
            pages = decisions_data.get("pages")
            if not isinstance(pages, list):
                problems.append("storyboard decisions have no page list")
            else:
                try:
                    expected = list(range(1, int(review.get("pages") or 0) + 1))
                except (TypeError, ValueError):
                    expected = []
                numbers = sorted(
                    int(row.get("page") or 0)
                    for row in pages
                    if isinstance(row, dict)
                )
                if numbers != expected:
                    problems.append(
                        "storyboard decisions do not cover every page exactly once"
                    )
                if any(
                    str(row.get("decision") or "") != "approve"
                    for row in pages
                    if isinstance(row, dict)
                ):
                    problems.append("storyboard decisions contain a non-approved page")
            if not _real_file(root, page) or review.get("page_sha256") != _sha(page):
                problems.append("storyboard review page is missing or changed")
            if decisions_data.get("html_sha256") != review.get("page_sha256"):
                problems.append("storyboard decisions were made against another page")
            if not _real_file(root, decisions_path) or review.get(
                "decisions_sha256"
            ) != _sha(decisions_path):
                problems.append("storyboard decisions are missing or changed")
    return problems
