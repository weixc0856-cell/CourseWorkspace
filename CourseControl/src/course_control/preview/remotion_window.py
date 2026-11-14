"""Render a time window of a Remotion composition at preview scale.

The window is the unit of preview: a shot, a segment or the whole film.  Using
Remotion's ``--frames`` and ``--scale`` keeps the composition, layout, fonts,
animation and audio exactly as the release render sees them; only the raster is
smaller.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.platform.timeouts import resolve_timeout
from course_control.platform.utils import load_json, probe_media, run_command, which_command
from course_control.preview.profile import PreviewProfile


@dataclass
class WindowResult:
    unit_id: str
    path: Path | None
    status: str
    duration_ms: int = 0
    key: str | None = None
    warnings: list[str] | None = None
    detail: str | None = None
    frames: str | None = None


def _sha(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _safe(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in value)
    return cleaned[:64] or "unit"


def _props_for(paths: LessonPaths, target: Path) -> Path:
    """Write preview props with build-root-relative asset paths."""
    timeline = paths.build_root / "contracts" / "timeline.spec.json"
    shots = paths.build_root / "shots.json"
    timeline_mode = paths.lesson.compose.renderer == "timeline" and timeline.is_file()
    source = timeline if timeline_mode else shots
    data = load_json(source)
    if timeline_mode:
        for key in ("video", "audio"):
            for item in data.get(key) or []:
                asset = item.get("asset") if isinstance(item, dict) else None
                if isinstance(asset, dict) and asset.get("path"):
                    candidate = Path(str(asset["path"]))
                    if not candidate.is_absolute():
                        base = (
                            paths.build_root.parent.parent
                            if candidate.parts and candidate.parts[0] == "build"
                            else paths.workspace
                        )
                        candidate = base / candidate
                    try:
                        asset["path"] = candidate.resolve().relative_to(
                            paths.build_root.resolve()
                        ).as_posix()
                    except (OSError, ValueError):
                        pass
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def _stage_assets(paths: LessonPaths, props: Path) -> tuple[str | None, list[str]]:
    """Copy every asset the composition reads into Remotion's staging folder.

    ``stage-assets.mjs`` resolves paths against the workspace, which is wrong
    when the content root sits outside it.  Doing the copy here uses the build
    root directly and keeps previews working in both layouts.

    Missing picture is an error.  Missing audio or subtitles is a warning and
    the item is removed, so a silent lesson still previews instead of failing.
    """
    data = load_json(props)
    staging = paths.workspace / "RemotionStudio" / "public" / "staging" / paths.slug
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    changed = False

    def copy(source: str) -> bool:
        raw = Path(source)
        src = raw if raw.is_absolute() else paths.build_root / raw
        if not src.is_file():
            return False
        dst = staging / source
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    if "video" in data or "audio" in data:
        for key in ("video", "audio"):
            kept = []
            for item in data.get(key) or []:
                asset = item.get("asset") if isinstance(item, dict) else None
                source = asset.get("path") if isinstance(asset, dict) else None
                if not source:
                    kept.append(item)
                    continue
                if copy(str(source)):
                    kept.append(item)
                elif key == "video":
                    return f"cannot stage {paths.build_root / str(source)}", warnings
                else:
                    warnings.append(f"preview without audio: {source}")
                    changed = True
            data[key] = kept
    else:
        shots = []
        for shot in data.get("shots") or []:
            source = shot.get("source") if isinstance(shot, dict) else None
            if source and not copy(str(source)):
                return f"cannot stage {paths.build_root / str(source)}", warnings
            shots.append(shot)
        data["shots"] = shots
        for key in ("narration", "subtitles"):
            item = data.get(key)
            source = item.get("path") if isinstance(item, dict) else None
            if source and not copy(str(source)):
                warnings.append(f"preview without {key}: {source}")
                data[key] = None
                changed = True
    if changed:
        props.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
        )
    return None, warnings


def _asset_signature(data: dict, build_root: Path) -> str:
    parts: list[str] = []
    for key in ("video", "audio"):
        for item in data.get(key) or []:
            asset = item.get("asset") if isinstance(item, dict) else None
            if not isinstance(asset, dict):
                continue
            raw = asset.get("path")
            if not raw:
                continue
            path = Path(str(raw))
            if not path.is_absolute():
                path = build_root / path
            try:
                stat = path.stat()
                parts.append(f"{path}:{stat.st_size}:{int(stat.st_mtime)}")
            except OSError:
                parts.append(f"{path}:missing")
    for key in ("narration", "subtitles"):
        item = data.get(key)
        if isinstance(item, dict) and item.get("path"):
            path = Path(str(item["path"]))
            if not path.is_absolute():
                path = build_root / path
            try:
                stat = path.stat()
                parts.append(f"{key}:{stat.st_size}:{int(stat.st_mtime)}")
            except OSError:
                parts.append(f"{key}:missing")
    return _sha("\n".join(parts))


def _downscale(
    source: Path,
    target: Path,
    profile: PreviewProfile,
    workspace: Path,
) -> tuple[Path | None, str | None]:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale={profile.width}:{profile.height}:flags=lanczos",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(target),
        ],
        workspace,
        timeout=600,
        log_path=target.parent.parent / "logs" / "preview-downscale.log",
    )
    if result.exit_code != 0:
        return None, f"downscale failed: {result.stderr[-800:]}"
    source.unlink(missing_ok=True)
    return target, None


def render_window(
    *,
    unit_id: str,
    workspace: Path,
    remotion_root: Path,
    entry: str,
    composition: str,
    output: Path,
    start_frame: int,
    end_frame: int,
    profile: PreviewProfile,
    props: Path | None = None,
    timeout_s: float | None = None,
    log_path: Path | None = None,
    force: bool = False,
) -> WindowResult:
    """Render ``[start_frame, end_frame)`` of one composition into ``output``.

    The caller owns staging and props generation because a lesson and a topic
    project resolve them differently.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    meta_path = output.with_suffix(".meta.json")
    props_signature = ""
    if props is not None and props.is_file():
        props_signature = _sha(props.read_bytes())
    frames = f"{start_frame}-{max(start_frame, end_frame - 1)}"
    key = _sha(
        "\n".join(
            [
                str(remotion_root.resolve()),
                entry,
                composition,
                frames,
                f"{profile.scale:.6f}",
                str(profile.fps),
                props_signature,
            ]
        )
    )
    if not force and output.is_file() and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        if meta.get("key") == key and output.stat().st_size > 0:
            return WindowResult(unit_id, output, "cached", key=key, frames=frames)

    started = time.monotonic()
    rendered = output
    if profile.is_preview:
        rendered = output.with_name(output.stem + ".render" + output.suffix)
    command = [
        *which_command("npx"),
        "remotion",
        "render",
        entry,
        composition,
        str(rendered),
        f"--frames={frames}",
        f"--scale={profile.render_scale:.4f}",
        "--timeout=120000",
    ]
    if props is not None:
        command.append(f"--props={props}")
    if not profile.audio:
        command.append("--muted")
    concurrency = os.environ.get("COURSEWORKSPACE_RENDER_CONCURRENCY")
    if concurrency:
        command.append(f"--concurrency={concurrency}")
    result = run_command(
        command,
        remotion_root,
        timeout=timeout_s or 900,
        log_path=log_path,
        env={"REMOTION_PREVIEW": "1"},
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.exit_code != 0:
        return WindowResult(
            unit_id,
            None,
            "failed",
            duration_ms=duration_ms,
            key=key,
            frames=frames,
            detail=f"remotion exited {result.exit_code}: {result.stderr[-1500:]}",
        )
    if not rendered.is_file() or rendered.stat().st_size == 0:
        return WindowResult(
            unit_id, None, "failed", duration_ms=duration_ms, key=key, frames=frames,
            detail="remotion produced no file",
        )
    if rendered != output:
        scaled, error = _downscale(rendered, output, profile, workspace)
        if scaled is None:
            return WindowResult(
                unit_id, None, "failed", duration_ms=duration_ms, key=key, frames=frames,
                detail=error or "downscale failed",
            )
    warnings: list[str] = []
    try:
        info = probe_media(output)
        if info.width and abs(info.width - profile.width) > 2:
            warnings.append(f"width {info.width} != {profile.width}")
        if info.height and abs(info.height - profile.height) > 2:
            warnings.append(f"height {info.height} != {profile.height}")
    except Exception as exc:  # noqa: BLE001 - a probe failure is a warning, not a pass
        warnings.append(f"probe failed: {exc}")
    meta_path.write_text(
        json.dumps(
            {
                "key": key,
                "unit": unit_id,
                "entry": entry,
                "composition": composition,
                "frames": frames,
                "profile": profile.as_dict(),
                "duration_ms": duration_ms,
                "mode": "preview" if profile.is_preview else "release",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return WindowResult(
        unit_id,
        output,
        "ok",
        duration_ms=duration_ms,
        key=key,
        warnings=warnings,
        frames=frames,
    )


def render_lesson_window(
    paths: LessonPaths,
    *,
    unit_id: str,
    start_s: float,
    end_s: float,
    profile: PreviewProfile,
    composition: str,
    entry: str = "src/index.ts",
    force: bool = False,
    output_dir: Path | None = None,
) -> WindowResult:
    """Lesson wrapper: stage assets, write props, render the window."""
    out_dir = output_dir or (
        paths.build_root
        / ("release" if profile.mode.value == "release" else "preview")
        / ("shot" if profile.level.value == "shot" else profile.level.value)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    props = _props_for(paths, paths.build_root / "preview" / "render-props.json")
    stage_error, stage_warnings = _stage_assets(paths, props)
    if stage_error:
        return WindowResult(unit_id, None, "failed", detail=stage_error)
    data = load_json(props)
    data["_preview_asset_signature"] = _asset_signature(data, paths.build_root)
    props.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fps = profile.fps
    start_frame = max(0, int(round(start_s * fps)))
    end_frame = max(start_frame + 1, int(round(end_s * fps)))
    result = render_window(
        unit_id=unit_id,
        workspace=paths.workspace,
        remotion_root=paths.workspace / "RemotionStudio",
        entry=entry,
        composition=composition,
        output=out_dir / f"{_safe(unit_id)}.mp4",
        start_frame=start_frame,
        end_frame=end_frame,
        profile=profile,
        props=props,
        timeout_s=resolve_timeout(paths, "compose"),
        log_path=paths.build_root / "preview" / "logs" / f"{_safe(unit_id)}.log",
        force=force,
    )
    if stage_warnings:
        result.warnings = list(result.warnings or []) + stage_warnings
    return result


__all__ = ["WindowResult", "render_lesson_window", "render_window"]
