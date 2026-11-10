"""Resolve the configuration used by one build into a single snapshot.

Production behaviour can be influenced by ``lesson.yaml``, five files under
``config/``, and environment variables. Reading them independently in each
module is how one lesson ends up with four different durations. This module
reads every source once, records the winning value and its source, and writes
an immutable ``build/<slug>/logs/config-resolution.json``.

The snapshot is also the configuration identity used by build resume: a
checkpoint is only reusable when the fingerprint is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .atomic import write_json_atomic
from .paths import LessonPaths

SCHEMA_VERSION = 1

CONFIG_FILES = {
    "tools": "config/tools.yaml",
    "local-paths": "config/local-paths.yaml",
    "model-routing": "config/model-routing.yaml",
    "content-qa": "config/content-qa.yaml",
    "authoring": "config/authoring.yaml",
    "claude-code": "config/claude-code.yaml",
}

CJK_RE = re.compile("[㐀-鿿]")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _dig(data: dict, dotted: str):
    value = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _relative(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace).as_posix()
    except (OSError, ValueError):
        return str(path)


def _srt_languages(path: Path) -> list[str]:
    """Languages actually present in an SRT, not the ones declared in YAML."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    spoken = [
        line
        for line in text.splitlines()
        if line.strip() and "-->" not in line and not line.strip().isdigit()
    ]
    languages: list[str] = []
    if any(CJK_RE.search(line) for line in spoken):
        languages.append("zh")
    if any(re.search("[A-Za-z]", line) and not CJK_RE.search(line) for line in spoken):
        languages.append("en")
    return languages


def _duration_facts(paths: LessonPaths) -> dict:
    lesson = paths.lesson
    policy = lesson.duration
    measured = None
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pages = meta.get("pages") or []
            if pages:
                measured = float(pages[-1].get("end_s") or 0.0) or None
            if measured is None:
                segments = meta.get("segments") or []
                if segments:
                    measured = max(float(item.get("end_s") or 0.0) for item in segments)
        except (OSError, ValueError, TypeError):
            measured = None
    timeline = None
    timeline_path = paths.build_root / "contracts" / "timeline.spec.json"
    if timeline_path.is_file():
        try:
            data = json.loads(timeline_path.read_text(encoding="utf-8"))
            fps = data.get("fps") or {}
            frames = data.get("total_frames")
            if frames and fps.get("fps_den"):
                timeline = float(frames) * float(fps["fps_den"]) / float(fps["fps_num"])
        except (OSError, ValueError, TypeError, ZeroDivisionError):
            timeline = None
    return {
        "target_seconds": getattr(policy, "target_seconds", None),
        "min_seconds": getattr(policy, "min_seconds", None),
        "max_seconds": getattr(policy, "max_seconds", None),
        "measured_seconds": measured,
        "timeline_seconds": timeline,
        # D-032: the measured narration is the authority once it exists.
        "authority": "measured" if measured else "target",
    }


def _add(values: list, key: str, value, source: str, note: str | None = None) -> None:
    values.append({"key": key, "value": value, "source": source, "note": note})


def _conflict(code: str, severity: str, message: str, **facts) -> dict:
    return {"code": code, "severity": severity, "message": message, **facts}


def resolve_config(workspace: Path, paths: LessonPaths) -> dict:
    workspace = workspace.resolve()
    lesson = paths.lesson
    lesson_rel = _relative(workspace, paths.lesson_dir / "lesson.yaml")

    sources: list[dict] = [
        {
            "name": "lesson",
            "path": lesson_rel,
            "present": True,
            "sha256": _sha256_file(paths.lesson_dir / "lesson.yaml"),
        }
    ]
    loaded: dict[str, dict] = {}
    for name, relative in CONFIG_FILES.items():
        path = workspace / relative
        loaded[name] = _load(path)
        sources.append(
            {
                "name": name,
                "path": relative,
                "present": path.is_file(),
                "sha256": _sha256_file(path),
            }
        )

    values: list[dict] = []
    _add(values, "compose.mode", lesson.compose.mode, lesson_rel)
    _add(values, "compose.renderer", lesson.compose.renderer, lesson_rel)
    _add(values, "engines", list(lesson.engines), lesson_rel)
    _add(values, "outputs.fps", lesson.outputs.fps, lesson_rel)
    _add(values, "outputs.resolution", list(lesson.outputs.resolution), lesson_rel)
    _add(values, "subtitles.enabled", lesson.subtitles.enabled, lesson_rel)
    _add(values, "subtitles.render", lesson.subtitles.render, lesson_rel)
    _add(values, "subtitles.bilingual", lesson.subtitles.bilingual, lesson_rel)
    _add(values, "subtitles.top_language", lesson.subtitles.top_language, lesson_rel)
    _add(values, "subtitles.bottom_language", lesson.subtitles.bottom_language, lesson_rel)
    _add(values, "audio.content_kind", lesson.audio.content_kind, lesson_rel)
    _add(values, "narration.timing", lesson.narration.timing, lesson_rel)

    tools = loaded["tools"]
    _add(values, "tools.blender.executable", _dig(tools, "blender.executable"), "config/tools.yaml")
    _add(values, "tools.blender.timeout_seconds", _dig(tools, "blender.timeout_seconds"), "config/tools.yaml")
    local = loaded["local-paths"]
    for key in ("ai_root", "bgm_root", "tts.runtime_dir", "tts.voice_ref", "tts.voice_ref_en"):
        _add(values, "local-paths." + key, _dig(local, key), "config/local-paths.yaml")
    routing = loaded["model-routing"]
    remote = {
        "enabled": _dig(routing, "remote.enabled"),
        "provider": _dig(routing, "remote.provider"),
        "base_url": _dig(routing, "remote.base_url"),
        "model": _dig(routing, "remote.model"),
        "api_key_env": _dig(routing, "remote.api_key_env"),
        "vision_model": _dig(routing, "remote.vision_model"),
        "fallback_on": _dig(routing, "fallback.on"),
    }
    _add(values, "model-routing.remote", remote, "config/model-routing.yaml")
    key_env = remote.get("api_key_env")
    _add(
        values,
        "model-routing.remote.api_key_present",
        bool(key_env and os.environ.get(str(key_env))),
        "environment",
        note="presence only; the value is never recorded" if key_env else None,
    )
    _add(values, "content-qa.backend", _dig(loaded["content-qa"], "backend"), "config/content-qa.yaml")
    _add(values, "content-qa.model.model", _dig(loaded["content-qa"], "model.model"), "config/content-qa.yaml")
    _add(values, "authoring.backend", _dig(loaded["authoring"], "backend"), "config/authoring.yaml")
    _add(
        values,
        "authoring.claude_code_fallback",
        _dig(loaded["authoring"], "claude_code_fallback"),
        "config/authoring.yaml",
    )
    _add(values, "claude-code.model", _dig(loaded["claude-code"], "model"), "config/claude-code.yaml")

    duration = _duration_facts(paths)
    _add(values, "duration.target_seconds", duration["target_seconds"], lesson_rel)
    _add(values, "duration.min_seconds", duration["min_seconds"], lesson_rel)
    _add(values, "duration.max_seconds", duration["max_seconds"], lesson_rel)
    _add(values, "duration.measured_seconds", duration["measured_seconds"], "build/<slug>/narration/narration.meta.json")
    _add(values, "duration.authority", duration["authority"], "DECISIONS.md D-032")

    conflicts: list[dict] = []
    warnings: list[str] = []

    # C-08/C-24: declared subtitle languages must match the SRT that is built.
    subtitle_path = paths.subtitles_path()
    detected = _srt_languages(subtitle_path) if subtitle_path is not None else []
    if lesson.subtitles.enabled and subtitle_path is not None and subtitle_path.is_file():
        if lesson.subtitles.bilingual and not {"en", "zh"}.issubset(detected):
            conflicts.append(
                _conflict(
                    "subtitle_language_mismatch",
                    "blocking",
                    "lesson declares bilingual subtitles but the SRT does not contain both languages",
                    declared=["en", "zh-Hans"],
                    detected=detected,
                    path=_relative(workspace, subtitle_path),
                )
            )
        if not lesson.subtitles.bilingual and len(detected) > 1:
            conflicts.append(
                _conflict(
                    "subtitle_language_mismatch",
                    "blocking",
                    "lesson declares single-language subtitles but the SRT contains more than one language",
                    declared=[lesson.subtitles.bottom_language],
                    detected=detected,
                )
            )

    # Content kinds that never carry BGM must not declare a music bed.
    if lesson.audio.content_kind in {"formal_course", "news"} and lesson.audio.bgm:
        conflicts.append(
            _conflict(
                "bgm_policy_violation",
                "blocking",
                "formal courses and news must not declare BGM cues",
                content_kind=lesson.audio.content_kind,
                cues=[cue.track_id for cue in lesson.audio.bgm],
            )
        )

    # DeepSeek is pinned to flash; the config layer must not accept pro.
    if str(remote.get("provider") or "").lower() == "deepseek":
        for label in ("model", "vision_model"):
            value = remote.get(label)
            if value and value != "deepseek-flash":
                conflicts.append(
                    _conflict(
                        "deepseek_model_pinned",
                        "blocking",
                        f"DeepSeek {label}={value!r} is disabled; use deepseek-flash",
                    )
                )

    measured = duration["measured_seconds"]
    if measured is not None:
        low = duration["min_seconds"]
        high = duration["max_seconds"]
        if low is not None and measured < low:
            conflicts.append(
                _conflict(
                    "duration_outside_policy",
                    "blocking",
                    f"measured narration {measured:.2f}s is below min {low:.2f}s",
                )
            )
        if high is not None and measured > high:
            conflicts.append(
                _conflict(
                    "duration_outside_policy",
                    "blocking",
                    f"measured narration {measured:.2f}s is above max {high:.2f}s",
                )
            )
        target = duration["target_seconds"]
        tolerance = float(lesson.acceptance.duration_tolerance_seconds or 2.0)
        if target is not None and abs(measured - target) > tolerance:
            warnings.append(
                f"measured narration {measured:.2f}s differs from target {target:.2f}s "
                f"by {abs(measured - target):.2f}s; measured wins (D-032)"
            )
    elif lesson.narration.enabled and lesson.narration.timing == "measured":
        warnings.append("narration.timing=measured but narration.meta.json is missing")

    if lesson.compose.mode == "shots" and lesson.compose.renderer != "timeline":
        warnings.append("shots mode with a legacy renderer is supported but not normalized")
    timeline = duration["timeline_seconds"]
    if timeline is not None and measured is not None and abs(timeline - measured) > 0.5:
        warnings.append(
            f"timeline {timeline:.2f}s differs from measured narration {measured:.2f}s "
            "by more than 0.5s"
        )

    fingerprint_payload = {
        "sources": [(item["path"], item["sha256"]) for item in sources],
        "values": values,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        "schema_version": SCHEMA_VERSION,
        "lesson": paths.slug,
        "generated_at": _now(),
        "sources": sources,
        "values": values,
        "duration": duration,
        "conflicts": conflicts,
        "warnings": warnings,
        "fingerprint": fingerprint,
    }


def blocking_conflicts(report: dict) -> list[dict]:
    return [item for item in report.get("conflicts") or [] if item.get("severity") == "blocking"]


def write_snapshot(paths: LessonPaths, report: dict) -> Path:
    target = paths.build_root / "logs" / "config-resolution.json"
    return write_json_atomic(target, report)


__all__ = [
    "CONFIG_FILES",
    "blocking_conflicts",
    "resolve_config",
    "write_snapshot",
]
