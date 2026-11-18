"""Delivery packages for internal media samples.

A sample is not a lesson: it has no storyboard, no approvals and no
publication clearance.  It still needs the same delivery discipline — probe,
decode, black/freeze, subtitles, hashes and a re-verifiable manifest.  This
module makes that explicit with ``kind: media_sample`` and
``publication: false`` instead of pretending a sample is a course.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel
from course_control.platform.utils import probe_media, run_command, which_command
from course_control.platform.workspace_layout import content_root
from course_control.quality.media_qc import _measure_loudness, detect_black_freeze

PASS = "pass"
FAIL = "fail"
INCOMPLETE = "incomplete"
KIND = "media_sample"
SCHEMA_VERSION = 3


class MediaPackageError(ValueError):
    pass


class MediaExpectation(StrictModel):
    min_s: float = Field(gt=0)
    max_s: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    audio: bool = True

    @model_validator(mode="after")
    def _window(self):
        if self.max_s < self.min_s:
            raise ValueError("max_s must be greater than or equal to min_s")
        return self


class MediaSampleSpec(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    title: str = Field(min_length=1)
    video: str = Field(min_length=1)
    subtitles: str | None = None
    scope: Literal["internal_sample"] = "internal_sample"
    publication: Literal[False] = False
    expected: MediaExpectation
    evidence: list[str] = Field(default_factory=list)
    notes: str | None = None


def load_media_spec(path: Path) -> MediaSampleSpec:
    path = Path(path)
    if not path.is_file():
        raise MediaPackageError(f"media sample spec not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
        return MediaSampleSpec.model_validate(data)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise MediaPackageError(f"invalid media sample spec {path}: {exc}") from exc


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(root) / path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _srt_coverage(path: Path) -> dict:
    """Return cue count and the union of cue intervals, in seconds."""
    import re

    text = Path(path).read_text(encoding="utf-8")
    pattern = re.compile(
        r"(\d\d):(\d\d):(\d\d),(\d+)\s*-->\s*(\d\d):(\d\d):(\d\d),(\d+)"
    )
    intervals: list[tuple[float, float]] = []
    for match in pattern.finditer(text):
        start = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 1000
        end = int(match.group(5)) * 3600 + int(match.group(6)) * 60 + int(match.group(7)) + int(match.group(8)) / 1000
        if end > start:
            intervals.append((start, end))
    intervals.sort()
    merged: list[list[float]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    covered = round(sum(end - start for start, end in merged), 3)
    return {"cues": len(intervals), "covered_s": covered, "last_end_s": round(merged[-1][1], 3) if merged else 0.0}


def check_media_sample(
    spec_path: Path,
    workspace: Path,
    *,
    root: Path | None = None,
) -> dict:
    spec = load_media_spec(spec_path)
    base = Path(root) if root is not None else content_root(Path(workspace).resolve())
    video = _resolve(base, spec.video)
    steps: list[dict] = []

    def add(step_id: str, status: str, detail: str, data: dict | None = None) -> None:
        steps.append({"id": step_id, "status": status, "detail": detail, "data": data or {}})

    if not video.is_file():
        add("final_video", INCOMPLETE, f"missing: {video}")
        return {"schema_version": 1, "kind": "media_sample_check", "id": spec.id, "status": INCOMPLETE, "steps": steps, "video": str(video)}
    try:
        info = probe_media(video)
    except Exception as exc:  # noqa: BLE001
        add("media_probe", FAIL, f"cannot probe: {exc}")
        return {"schema_version": 1, "kind": "media_sample_check", "id": spec.id, "status": FAIL, "steps": steps, "video": str(video)}

    add("final_video", PASS, str(video))
    add("media_probe", PASS, f"{info.width}x{info.height} {info.duration:.2f}s fps={info.fps} audio={info.has_audio}", info.as_dict())

    problems = []
    if info.duration is None or not (spec.expected.min_s <= info.duration <= spec.expected.max_s):
        problems.append(f"duration {info.duration} outside [{spec.expected.min_s}, {spec.expected.max_s}]")
    if info.width != spec.expected.width or info.height != spec.expected.height:
        problems.append(f"resolution {info.width}x{info.height} != {spec.expected.width}x{spec.expected.height}")
    if info.fps is None or abs(info.fps - spec.expected.fps) > 0.01:
        problems.append(f"fps {info.fps} != {spec.expected.fps}")
    if bool(info.has_audio) != spec.expected.audio:
        problems.append(f"audio {info.has_audio} != {spec.expected.audio}")
    add("expected", FAIL if problems else PASS, "; ".join(problems) or "duration, resolution, fps and audio match")

    decode = run_command(
        [*which_command("ffmpeg"), "-v", "error", "-i", str(video), "-f", "null", "-"],
        Path(workspace).resolve(),
        timeout=1800,
    )
    add("decode", PASS if decode.exit_code == 0 and not decode.stderr.strip() else FAIL, decode.stderr[-800:] or "full decode ok")

    if info.has_audio:
        loudness = _measure_loudness(video, Path(workspace).resolve())
        add(
            "loudness",
            PASS if loudness.get("integrated_lufs") is not None else INCOMPLETE,
            f"{loudness.get('integrated_lufs')} LUFS / {loudness.get('true_peak_dbfs')} dBTP",
            loudness,
        )
    else:
        add("loudness", INCOMPLETE, "no audio stream")

    black, freeze = detect_black_freeze(video, Path(workspace).resolve(), video.parent / "media-qc-blackfreeze.log")
    add("black", FAIL if black else PASS, f"{len(black)} black interval(s)", {"intervals": black[:20]})
    add("freeze", PASS, f"{len(freeze)} frozen interval(s); review intentional holds", {"intervals": freeze[:20]})

    subtitle_info = None
    if spec.subtitles:
        subtitle_path = _resolve(base, spec.subtitles)
        if not subtitle_path.is_file():
            add("subtitles", INCOMPLETE, f"missing: {subtitle_path}")
        else:
            subtitle_info = _srt_coverage(subtitle_path)
            add(
                "subtitles",
                PASS,
                f"{subtitle_info['cues']} cues, {subtitle_info['covered_s']}s covered, last end {subtitle_info['last_end_s']}s",
                subtitle_info,
            )
    else:
        add("subtitles", INCOMPLETE, "no sidecar subtitles declared")

    missing_evidence = []
    for item in spec.evidence:
        path = _resolve(base, item)
        if not path.is_file():
            missing_evidence.append(str(path))
    add(
        "evidence",
        INCOMPLETE if missing_evidence else PASS,
        "; ".join(missing_evidence) or f"{len(spec.evidence)} evidence file(s) present",
    )

    status = FAIL if any(step["status"] == FAIL for step in steps) else (
        INCOMPLETE if any(step["status"] == INCOMPLETE for step in steps) else PASS
    )
    return {
        "schema_version": 1,
        "kind": "media_sample_check",
        "id": spec.id,
        "title": spec.title,
        "scope": spec.scope,
        "publication": spec.publication,
        "status": status,
        "video": str(video),
        "subtitles": str(_resolve(base, spec.subtitles)) if spec.subtitles else None,
        "subtitle_coverage": subtitle_info,
        "steps": steps,
    }


def _record(root: Path, path: Path, required: bool = True) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "required": required,
        "status": "present",
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _copy(root: Path, source: Path, relative: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def build_media_package(
    spec_path: Path,
    workspace: Path,
    *,
    root: Path | None = None,
) -> tuple[dict, Path]:
    base = Path(root) if root is not None else content_root(Path(workspace).resolve())
    check = check_media_sample(spec_path, workspace, root=base)
    if check["status"] != PASS:
        reasons = "; ".join(
            f"{step['id']}={step['status']}" for step in check["steps"] if step["status"] != PASS
        )
        raise MediaPackageError(f"release check is {check['status']}: {reasons}")
    spec = load_media_spec(spec_path)
    video = Path(check["video"])
    target = base / "deliver" / spec.id
    scratch = target.with_name(target.name + ".tmp")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    records = [_record(scratch, _copy(scratch, video, "final/master.mp4"))]
    if check.get("subtitles"):
        source = Path(check["subtitles"])
        suffix = source.suffix or ".srt"
        records.append(_record(scratch, _copy(scratch, source, f"final/subtitles{suffix}")))
    for index, item in enumerate(spec.evidence, start=1):
        source = _resolve(base, item)
        try:
            relative = source.relative_to(base).as_posix()
        except ValueError:
            relative = f"external/{index:02d}-{source.name}"
        records.append(_record(scratch, _copy(scratch, source, f"evidence/{relative}")))
    info = probe_media(video)
    metadata = {
        "schema_version": 1,
        "kind": KIND,
        "id": spec.id,
        "title": spec.title,
        "scope": spec.scope,
        "publication": spec.publication,
        "generated_at": _now(),
        "duration_s": info.duration,
        "resolution": [info.width, info.height],
        "fps": info.fps,
        "audio": info.has_audio,
        "subtitle_coverage": check.get("subtitle_coverage"),
        "notes": spec.notes,
    }
    (scratch / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records.append(_record(scratch, scratch / "metadata.json"))
    checklist = [
        f"# Media sample delivery — {spec.id}",
        "",
        f"- scope: `{spec.scope}`",
        f"- publication: `{spec.publication}`",
        f"- master: `final/master.mp4` ({info.duration} s, {info.width}x{info.height})",
        f"- verdict: `pass`",
        f"- subtitles: `{check.get('subtitles') or 'none'}`",
        "",
        "| file | required | bytes | sha256 |",
        "| --- | --- | ---: | --- |",
        *[f"| {item['path']} | {item['required']} | {item['bytes']} | {item['sha256'][:16]}… |" for item in records],
    ]
    (scratch / "delivery-checklist.md").write_text("\n".join(checklist) + "\n", encoding="utf-8")
    records.append(_record(scratch, scratch / "delivery-checklist.md"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "id": spec.id,
        "title": spec.title,
        "scope": spec.scope,
        "publication": spec.publication,
        "generated_at": _now(),
        "verdict": "pass",
        "verdict_reasons": [],
        "expected": spec.expected.model_dump(),
        "probe": info.as_dict(),
        "subtitle_coverage": check.get("subtitle_coverage"),
        "checks": check["steps"],
        "files": records,
    }
    manifest_path = scratch / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    backup = target.with_name(target.name + ".old")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        target.rename(backup)
    scratch.rename(target)
    if backup.exists():
        shutil.rmtree(backup)
    return manifest, target


def verify_media_package(root: Path) -> list[str]:
    root = Path(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest.json is unreadable: {exc}"]
    if not isinstance(manifest, dict) or manifest.get("kind") != KIND:
        return ["manifest is not a media_sample package"]
    if manifest.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version is {manifest.get('schema_version')!r}, expected {SCHEMA_VERSION}"]
    if manifest.get("verdict") != "pass":
        return [f"verdict is {manifest.get('verdict')!r}, not pass"]
    if manifest.get("publication") is not False:
        return ["media_sample package must declare publication: false"]
    problems: list[str] = []
    for item in manifest.get("files") or []:
        if not isinstance(item, dict):
            problems.append("file record is not an object")
            continue
        path = root / str(item.get("path") or "")
        if not path.is_file():
            if item.get("required"):
                problems.append(f"missing required file: {item.get('path')}")
            continue
        if item.get("sha256") != _sha(path):
            problems.append(f"sha256 mismatch: {item.get('path')}")
        if item.get("bytes") != path.stat().st_size:
            problems.append(f"size mismatch: {item.get('path')}")
    if not (root / "final" / "master.mp4").is_file():
        problems.append("final/master.mp4 is missing")
    return problems
