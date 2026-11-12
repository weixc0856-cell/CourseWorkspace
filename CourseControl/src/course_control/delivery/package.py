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


def build_package(paths: LessonPaths, output_root: Path | None = None) -> tuple[dict, Path]:
    """Collect a delivery package and return (manifest, package_root).

    Raises ``PackageError`` when a required artifact is missing or unreadable.
    Optional artifacts are recorded as ``not_applicable`` instead of being
    invented.
    """
    build_root = paths.build_root
    final_root = (output_root or paths.delivery_root).resolve()
    if not is_under(paths.workspace, final_root):
        raise PackageError(f"package output must stay inside the workspace: {final_root}")
    # Build beside the target and swap only after the new package is complete.
    # A failed run must never destroy the last valid delivery package.
    root = final_root.with_name(final_root.name + ".tmp")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    build_report = build_root / "final" / "build-report.json"
    media_qc = build_root / "quality" / "media-qc.json"
    narration_meta = build_root / "narration" / "narration.meta.json"
    final = _final_video(paths)

    required: list[tuple[str, Path, Path | None]] = [
        ("final/master.mp4", final, final),
        ("build-report.json", build_report, build_report),
        ("evidence/media-qc.json", media_qc, media_qc),
    ]
    if paths.lesson.narration.enabled:
        required.append(("narration.meta.json", narration_meta, narration_meta))

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

    manifest = {
        "schema_version": 1,
        "lesson": paths.slug,
        "run_id": run_id,
        "generated_at": _now(),
        "verdict": "pass",
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
    return manifest, final_root


def verify_package(root: Path) -> list[str]:
    """Re-hash every file in a package and report mismatches."""
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json is unreadable: {exc}"]
    problems: list[str] = []
    for item in manifest.get("files") or []:
        path = root / str(item.get("path") or "")
        if item.get("status") != "present":
            if item.get("required"):
                problems.append(f"missing required: {item.get('path')}")
            continue
        if not path.is_file():
            problems.append(f"missing: {item.get('path')}")
            continue
        if item.get("sha256") and _sha(path) != item["sha256"]:
            problems.append(f"hash mismatch: {item.get('path')}")
    for item in manifest.get("external_assets") or []:
        relative = item.get("bundled_path")
        path = root / str(relative or "")
        if not relative or not path.is_file():
            problems.append(f"missing bundled asset: {relative or item.get('asset_id')}")
            continue
        if item.get("sha256") and _sha(path) != item["sha256"]:
            problems.append(f"hash mismatch: {relative}")
    return problems
