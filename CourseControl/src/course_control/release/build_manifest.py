"""Content fingerprints for an episode film.

A film is current when its content still matches the content it was rendered
from.  mtime can say "newer" for a file that was touched, copied or checked out
and "older" for a re-render that produced the same picture; neither answers the
question.  This module hashes the declared inputs and the output, gives the
combination a build id, and lets release-check compare hashes first.  Only when
no manifest exists does it fall back to mtimes, and then the verdict says so.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from course_control.content.paths import LessonPaths

MANIFEST_NAME = "manifest.json"
FINGERPRINT = "fingerprint"
MTIME_WEAK = "mtime (weak)"
MANIFEST_WEAK = "manifest (weak)"


class BuildManifestError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(paths: LessonPaths) -> Path:
    return paths.build_root / MANIFEST_NAME


def declared_inputs(
    paths: LessonPaths,
    workspace: Path,
    *,
    timing: Path | None = None,
    meta: Path | None = None,
) -> list[tuple[str, Path]]:
    """The inputs a re-render must consume for the film to stay current."""
    timing_path = timing or (workspace / "RemotionStudio" / "src" / "episode" / "timing.json")
    meta_path = meta or (paths.build_root / "narration" / "narration.resequenced.meta.json")
    subtitles = paths.subtitles_path()
    entries = [
        ("lesson", paths.lesson_dir / "lesson.yaml"),
        ("episode_spec", paths.lesson_dir / "authoring" / "episode.spec.yaml"),
        ("quality_rubric", paths.lesson_dir / "authoring" / "quality.rubric.yaml"),
        ("storyboard", getattr(paths, "storyboard_source", None)),
        ("production", getattr(paths, "production_source", None)),
        (
            "slides",
            paths.lesson_dir / getattr(getattr(paths, "lesson", None), "content", None).slides
            if getattr(getattr(getattr(paths, "lesson", None), "content", None), "slides", None)
            else None,
        ),
        ("timing", Path(timing_path)),
        ("narration_meta", Path(meta_path)),
        ("subtitles", Path(subtitles) if subtitles is not None else None),
    ]
    # The sign-off exists only after the storyboard gate; include it when it is
    # there so a later sign-off, page edit or review edit changes the build id.
    for name, relative in (
        ("storyboard_review", "authoring/storyboard-review.json"),
        ("storyboard_review_page", "authoring/storyboard-review.html"),
        ("storyboard_decisions", "authoring/storyboard-decisions.json"),
    ):
        candidate = paths.lesson_dir / relative
        if candidate.is_file():
            entries.append((name, candidate))
    design = paths.build_root / "design" / "visual_design.json"
    if design.is_file():
        entries.append(("visual_design", design))
    slides_dir = paths.build_root / "slides"
    if slides_dir.is_dir():
        for capture in sorted(slides_dir.glob("*.png")):
            entries.append((f"slide_capture:{capture.name}", capture))
    return [(name, path) for name, path in entries if path is not None]


def fingerprint(
    paths: LessonPaths,
    workspace: Path,
    *,
    timing: Path | None = None,
    meta: Path | None = None,
) -> dict:
    """Hash the declared inputs and derive a stable build id."""
    entries = []
    missing = []
    for name, path in declared_inputs(paths, workspace, timing=timing, meta=meta):
        path = path.resolve()
        if not path.is_file():
            missing.append({"name": name, "path": str(path)})
            continue
        entries.append(
            {
                "name": name,
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    if missing:
        raise BuildManifestError(
            "missing inputs: " + ", ".join(f"{item['name']} ({item['path']})" for item in missing)
        )
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(f"{entry['name']}:{entry['sha256']}\n".encode("utf-8"))
    return {"build_id": digest.hexdigest()[:12], "digest": digest.hexdigest(), "inputs": entries}


def write_manifest(
    paths: LessonPaths,
    workspace: Path,
    video: Path,
    *,
    timing: Path | None = None,
    meta: Path | None = None,
    render: dict | None = None,
    allow_older: bool = False,
) -> dict:
    """Record the inputs and the rendered film as one build.

    A film older than one of its inputs cannot have been rendered from it; the
    manifest refuses to bless that pairing unless the caller says so.
    """
    video = Path(video).resolve()
    if not video.is_file():
        raise BuildManifestError(f"video not found: {video}")
    data = fingerprint(paths, workspace, timing=timing, meta=meta)
    if not allow_older:
        video_time = video.stat().st_mtime
        newer = [
            entry["path"]
            for entry in data["inputs"]
            if Path(entry["path"]).stat().st_mtime > video_time
        ]
        if newer:
            raise BuildManifestError(
                "the film is older than its inputs and cannot be their output: "
                + ", ".join(newer)
            )
    payload = {
        "schema_version": 1,
        "kind": "episode_build",
        "lesson": paths.slug,
        "build_id": data["build_id"],
        "digest": data["digest"],
        "created_at": _now(),
        "inputs": data["inputs"],
        "output": {
            "path": str(video),
            "sha256": _sha256(video),
            "bytes": video.stat().st_size,
        },
        "forced": bool(allow_older),
        "publishable": not allow_older,
        "render": render or {},
    }
    target = manifest_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


@dataclass
class Freshness:
    fresh: bool
    stale_by: str
    build_id: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "fresh": self.fresh,
            "stale_by": self.stale_by,
            "build_id": self.build_id,
            "reason": self.reason,
        }


def _mtime_freshness(paths: LessonPaths, video: Path) -> Freshness:
    """Weak fallback: the film must be newer than every current input file.

    If the current input set cannot even be enumerated, the answer is stale:
    the old hard-coded input list let a renamed or moved input read as fresh.
    """
    try:
        inputs = declared_inputs(paths, paths.workspace)
    except (AttributeError, OSError) as exc:
        return Freshness(
            False,
            MTIME_WEAK,
            reason=f"stale: cannot evaluate the declared inputs: {exc}",
        )
    video_time = video.stat().st_mtime
    for name, item in inputs:
        if not item.is_file():
            return Freshness(
                False,
                MTIME_WEAK,
                reason=f"stale: declared input is missing: {name} ({item})",
            )
        if item.stat().st_mtime > video_time:
            return Freshness(
                False,
                MTIME_WEAK,
                reason=(
                    f"stale: {video} (mtime {video_time:.0f}) is older than "
                    f"{item} (mtime {item.stat().st_mtime:.0f})"
                ),
            )
    return Freshness(True, MTIME_WEAK, reason=None)


def check_freshness(paths: LessonPaths, video: Path) -> Freshness:
    """Compare the film with the build manifest, falling back to mtimes."""
    path = manifest_path(paths)
    if not path.is_file():
        return _mtime_freshness(paths, video)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Freshness(False, MANIFEST_WEAK, reason=f"unreadable build manifest: {exc}")
    build_id = str(manifest.get("build_id") or "")
    if manifest.get("forced") or manifest.get("publishable") is False:
        return Freshness(
            False,
            FINGERPRINT,
            build_id,
            "stale: manifest was written with --force and is not publishable",
        )
    required_entries = dict(declared_inputs(paths, paths.workspace))
    declared = {
        str(entry.get("name") or ""): entry
        for entry in manifest.get("inputs") or []
        if isinstance(entry, dict)
    }
    missing = [name for name in required_entries if name not in declared]
    if missing:
        return Freshness(
            False,
            FINGERPRINT,
            build_id,
            "stale: build manifest predates required inputs: " + ", ".join(missing),
        )
    for name, current_path in required_entries.items():
        entry = declared[name]
        declared_path = Path(str(entry.get("path") or ""))
        if declared_path.resolve() != Path(current_path).resolve():
            return Freshness(
                False,
                FINGERPRINT,
                build_id,
                f"stale: input {name} now points at {current_path}, not {declared_path}",
            )
    for entry in manifest.get("inputs") or []:
        declared = Path(str(entry.get("path") or ""))
        if not declared.is_file():
            return Freshness(
                False,
                FINGERPRINT,
                build_id,
                f"stale: build input removed since build {build_id}: {declared}",
            )
        if _sha256(declared) != entry.get("sha256"):
            return Freshness(
                False,
                FINGERPRINT,
                build_id,
                f"stale: {declared} changed since build {build_id}; re-render before release",
            )
    try:
        current = fingerprint(paths, paths.workspace)
    except (BuildManifestError, OSError) as exc:
        return Freshness(False, FINGERPRINT, build_id, f"stale: current inputs are incomplete: {exc}")
    if current.get("digest") != manifest.get("digest"):
        return Freshness(
            False,
            FINGERPRINT,
            build_id,
            "stale: the current input digest differs from the build",
        )

    output = manifest.get("output") or {}
    rendered = Path(str(output.get("path") or ""))
    if not rendered.is_file():
        return Freshness(
            False,
            FINGERPRINT,
            build_id,
            f"stale: the film this manifest describes is gone: {rendered}",
        )
    if _sha256(video) != output.get("sha256"):
        return Freshness(
            False,
            FINGERPRINT,
            build_id,
            f"stale: {video} is not the film from build {build_id} (output hash differs)",
        )
    return Freshness(True, FINGERPRINT, build_id, None)


__all__ = [
    "BuildManifestError",
    "FINGERPRINT",
    "Freshness",
    "MANIFEST_WEAK",
    "MTIME_WEAK",
    "check_freshness",
    "declared_inputs",
    "fingerprint",
    "manifest_path",
    "write_manifest",
]
