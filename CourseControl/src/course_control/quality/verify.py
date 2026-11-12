from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from course_control.rendering.branding import DELIVERY_NAME, sha256_file
from course_control.content.contracts import CheckRecord, ShotsFile, Status
from course_control.content.duration import resolve, window_problem
from course_control.content.paths import LessonPaths, path_problem
from course_control.voice.subtitles import CuePolicy, display_width
from course_control.platform.utils import count_srt_cues, page_budgets, probe_media


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(check_id: str, ok: bool, expected: str, actual: str, detail: str | None = None) -> CheckRecord:
    return CheckRecord(
        id=check_id,
        status=Status.PASS if ok else Status.FAIL,
        expected=expected,
        actual=actual,
        detail=detail,
    )


def _brand_check(paths: LessonPaths, build_root: Path) -> CheckRecord:
    """V-36: the stitched delivery master equals body + brand segments.

    The check recomputes the expectation from `brand/plan.json` and the actual
    master probe; it never trusts `final/brand.json` on its own.
    """

    if not paths.lesson.branding.enabled:
        return CheckRecord(id="V-36", status=Status.NOT_APPLICABLE, detail="branding disabled")

    delivery = build_root / "final" / DELIVERY_NAME
    plan_file = build_root / "brand" / "plan.json"
    record_file = build_root / "final" / "brand.json"
    problems: list[str] = []
    if not delivery.is_file():
        problems.append(f"delivery missing: {delivery.name}")
    if not plan_file.is_file():
        problems.append("brand/plan.json missing")
    if not record_file.is_file():
        problems.append("final/brand.json missing")
    if problems:
        return _check("V-36", False, "delivery, plan and brand.json exist", "missing", "; ".join(problems))

    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        record = json.loads(record_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _check("V-36", False, "readable brand plan and record", "unreadable", str(exc))

    segments = plan.get("segments") or []
    brand_s = plan.get("brand_duration_s")
    master_name = plan.get("master")
    master = build_root / "final" / str(master_name or "")
    if not master_name or not master.is_file():
        problems.append(f"master missing: {master_name}")
    if brand_s is None or not segments:
        problems.append("plan has no brand segments")
    if problems:
        return _check("V-36", False, "branded master and plan", "missing", "; ".join(problems))

    try:
        body_info = probe_media(master)
        out_info = probe_media(delivery)
    except Exception as exc:  # noqa: BLE001
        return _check("V-36", False, "readable delivery", "probe failed", str(exc))

    fps = float(plan.get("fps") or paths.lesson.outputs.fps)
    tolerance = len(segments) / fps + 0.15
    expected = (body_info.duration or 0.0) + float(brand_s)
    if out_info.duration is None or abs(out_info.duration - expected) > tolerance:
        problems.append(
            f"duration {out_info.duration} != body+brand {expected:.3f}s"
        )
    if (out_info.width, out_info.height) != (body_info.width, body_info.height):
        problems.append("resolution differs from the master")
    if out_info.fps is None or body_info.fps is None or abs(out_info.fps - body_info.fps) > 0.01:
        problems.append("fps differs from the master")
    if out_info.has_audio != body_info.has_audio:
        problems.append("audio stream presence differs from the master")
    if record.get("mode") not in ("copy", "reencode"):
        problems.append(f"unknown stitch mode {record.get('mode')!r}")
    if record.get("master") != master_name:
        problems.append("brand.json records a different master")
    if record.get("sha256") and record["sha256"] != sha256_file(delivery):
        problems.append("delivery hash differs from brand.json")
    timing = record.get("video_timing") or {}
    if timing.get("status") == "fail":
        problems.append(
            "video timestamps are collapsed "
            f"({timing.get('clustered_intervals')} intervals below half a frame)"
        )
    alignment = record.get("audio_alignment") or {}
    if alignment.get("status") == "fail":
        problems.append(
            "body audio is offset by "
            f"{alignment.get('delta_s')}s (expected {alignment.get('expected_s')}s)"
        )
    if record.get("problems"):
        problems.append("brand.json lists problems")

    return _check(
        "V-36",
        not problems,
        f"delivery = body {body_info.duration}s + brand {float(brand_s)}s ± {tolerance:.2f}s",
        f"{out_info.duration}s via {record.get('mode')}" if out_info.duration is not None else "unknown",
        "; ".join(problems) if problems else None,
    )


def verify(paths: LessonPaths, shots_file: ShotsFile) -> list[CheckRecord]:
    checks: list[CheckRecord] = []
    build_root = paths.build_root
    final = build_root / "final" / "course-video.mp4"
    fps = shots_file.timeline.fps
    width, height = shots_file.timeline.resolution

    missing = []
    probes = {}
    for shot in shots_file.shots:
        source = (build_root / shot.source).resolve()
        if not source.is_file():
            missing.append(shot.source)
            continue
        try:
            probes[shot.source] = probe_media(source)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{shot.source} ({exc})")
    checks.append(
        _check(
            "V-10",
            not missing,
            "all shot sources exist and are readable",
            "ok" if not missing else ", ".join(missing),
        )
    )

    bad_media = []
    for shot in shots_file.shots:
        info = probes.get(shot.source)
        if info is None:
            continue
        if shot.kind in ("animation", "recording"):
            if info.width != width or info.height != height:
                bad_media.append(
                    f"{shot.id}: {info.width}x{info.height} != {width}x{height}"
                )
            if info.fps is not None and abs(info.fps - fps) > 0.01:
                bad_media.append(f"{shot.id}: {info.fps:.3f} fps != {fps}")
    checks.append(
        _check(
            "V-12",
            not bad_media,
            f"{width}x{height} @ {fps} fps",
            "ok" if not bad_media else "; ".join(bad_media),
        )
    )

    base = sorted(
        [shot for shot in shots_file.shots if shot.timeline_role == "base"],
        key=lambda item: item.start_s,
    )
    timeline_errors: list[str] = []
    cursor = 0.0
    for shot in base:
        if abs(shot.start_s - cursor) > 0.01:
            timeline_errors.append(f"{shot.id} starts at {shot.start_s}, expected {cursor}")
        cursor = shot.start_s + shot.duration_s
    if abs(cursor - shots_file.timeline.total_duration_s) > 0.01:
        timeline_errors.append(
            f"base ends at {cursor:.3f}, timeline says {shots_file.timeline.total_duration_s:.3f}"
        )
    overlays = [shot for shot in shots_file.shots if shot.timeline_role == "overlay"]
    for overlay in overlays:
        parent = next(
            (
                item
                for item in base
                if item.kind == "recording"
                and item.start_s - 1e-6 <= overlay.start_s
                and overlay.start_s + overlay.duration_s <= item.start_s + item.duration_s + 1e-6
            ),
            None,
        )
        if parent is None:
            parent = next(
                (
                    item
                    for item in base
                    if item.slide == overlay.slide
                    and item.start_s - 1e-6 <= overlay.start_s
                    and overlay.start_s + overlay.duration_s <= item.start_s + item.duration_s + 1e-6
                ),
                None,
            )
        if parent is None:
            # Scene mode uses one full-length base video without a slide id.
            parent = next(
                (
                    item
                    for item in base
                    if item.slide is None
                    and item.start_s - 1e-6 <= overlay.start_s
                    and overlay.start_s + overlay.duration_s <= item.start_s + item.duration_s + 1e-6
                ),
                None,
            )
        if parent is None:
            timeline_errors.append(f"{overlay.id} is not inside a base segment")
    for index, first in enumerate(overlays):
        for second in overlays[index + 1:]:
            if first.start_s < second.start_s + second.duration_s - 1e-6 and second.start_s < first.start_s + first.duration_s - 1e-6:
                timeline_errors.append(f"{first.id} overlaps {second.id}")
    checks.append(
        _check(
            "V-13",
            not timeline_errors,
            "base segments are contiguous; overlays fit and do not overlap",
            "ok" if not timeline_errors else "; ".join(timeline_errors),
        )
    )

    outside = [
        shot.source
        for shot in shots_file.shots
        if Path(shot.source).is_absolute() or ".." in Path(shot.source).parts
    ]
    checks.append(
        _check(
            "V-18",
            not outside,
            "all shot sources are relative to build/<lesson>/",
            "ok" if not outside else ", ".join(outside),
        )
    )

    path_issues: list[str] = []
    declared = [shot.source for shot in shots_file.shots]
    if shots_file.narration and shots_file.narration.get("path"):
        declared.append(str(shots_file.narration["path"]))
    if shots_file.subtitles and shots_file.subtitles.get("path"):
        declared.append(str(shots_file.subtitles["path"]))
    for value in declared:
        problem = path_problem(value)
        if problem:
            path_issues.append(f"{value}: {problem}")
    checks.append(
        _check(
            "V-21",
            not path_issues,
            "all declared paths are relative, / separated, without ..",
            "ok" if not path_issues else "; ".join(path_issues),
        )
    )

    if not final.is_file():
        checks.append(
            CheckRecord(
                id="V-14",
                status=Status.NOT_RUN,
                expected="final video exists",
                actual="missing",
                detail=str(final),
            )
        )
        return checks

    try:
        final_info = probe_media(final)
    except Exception as exc:  # noqa: BLE001
        checks.append(
            CheckRecord(
                id="V-14",
                status=Status.FAIL,
                expected="readable final video",
                actual="probe failed",
                detail=str(exc),
            )
        )
        return checks
    expected_duration = paths.lesson.acceptance.notes_total_seconds
    if expected_duration is None:
        if shots_file.timeline.total_duration_s:
            expected_duration = shots_file.timeline.total_duration_s
    tolerance = paths.lesson.acceptance.duration_tolerance_seconds
    duration_ok = (
        expected_duration is None
        or abs((final_info.duration or 0.0) - expected_duration) <= tolerance
    )
    checks.append(
        _check(
            "V-14",
            duration_ok,
            f"{expected_duration} ± {tolerance}s" if expected_duration is not None else "not applicable",
            f"{final_info.duration:.3f}s" if final_info.duration is not None else "unknown",
        )
    )

    if paths.lesson.subtitles.enabled and paths.lesson.subtitles.render == "burn_in":
        captioned = build_root / "final" / "course-video-captioned.mp4"
        if not captioned.is_file():
            checks.append(
                CheckRecord(
                    id="V-28",
                    status=Status.FAIL,
                    expected="captioned video exists",
                    actual="missing",
                    detail=str(captioned),
                )
            )
        else:
            try:
                captioned_info = probe_media(captioned)
            except Exception as exc:  # noqa: BLE001
                checks.append(
                    CheckRecord(
                        id="V-28",
                        status=Status.FAIL,
                        expected="readable captioned video",
                        actual="probe failed",
                        detail=str(exc),
                    )
                )
            else:
                frame = 1.0 / (fps or 30)
                problems: list[str] = []
                if (
                    final_info.duration is not None
                    and captioned_info.duration is not None
                    and abs(captioned_info.duration - final_info.duration) > frame + 0.05
                ):
                    problems.append(
                        f"duration {captioned_info.duration:.3f}s vs {final_info.duration:.3f}s"
                    )
                if (captioned_info.width, captioned_info.height) != (width, height):
                    problems.append("resolution differs")
                if captioned_info.fps != final_info.fps:
                    problems.append("fps differs")
                if captioned_info.has_audio != final_info.has_audio:
                    problems.append("audio stream presence differs")
                burn = build_root / "final" / "burn.json"
                if not burn.is_file():
                    problems.append("burn.json missing")
                checks.append(
                    _check(
                        "V-28",
                        not problems,
                        "captioned output matches clean master within one frame",
                        f"{captioned_info.duration:.3f}s" if captioned_info.duration is not None else "unknown",
                        "; ".join(problems) if problems else None,
                    )
                )
    else:
        checks.append(
            CheckRecord(id="V-28", status=Status.NOT_APPLICABLE, detail="burn-in disabled")
        )

    policy = resolve(paths.lesson)
    if policy is None:
        checks.append(
            CheckRecord(id="V-27", status=Status.NOT_APPLICABLE, detail="no duration policy")
        )
    else:
        problem = window_problem(final_info.duration or 0.0, policy)
        checks.append(
            _check(
                "V-27",
                problem is None,
                f"{policy.minimum:.1f}-{policy.maximum:.1f}s (target {policy.target:.1f}s)",
                f"{final_info.duration:.3f}s" if final_info.duration is not None else "unknown",
                problem.message if problem is not None else None,
            )
        )

    if paths.lesson.narration.enabled and paths.lesson.narration.timing == "measured":
        meta_path = build_root / "narration" / "narration.meta.json"
        if not meta_path.is_file():
            checks.append(
                CheckRecord(
                    id="V-30",
                    status=Status.FAIL,
                    expected="narration.meta.json exists",
                    actual="missing",
                    detail=str(meta_path),
                )
            )
        else:
            problems: list[str] = []
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                problems.append(f"cannot read meta: {exc}")
                meta = {}
            # v2 predates voice assets; v3 adds them.  Never pin the exact
            # number, or the next narration build fails verification.
            if int(meta.get("schema_version") or 0) < 2:
                problems.append("meta schema_version is older than 2")
            assembly = meta.get("assembly") or {}
            assembly_path = build_root / str(assembly.get("file") or "")
            if not assembly_path.is_file():
                problems.append("assembly file missing")
            else:
                assembly_duration = assembly.get("duration_s")
                if assembly_duration is None or abs(
                    float(assembly_duration) - shots_file.timeline.total_duration_s
                ) > 1.0 / (fps or 30) + 0.05:
                    problems.append("assembly duration differs from the frozen timeline")
            source = meta.get("source") or {}
            script_rel = paths.lesson.authoring.script if paths.lesson.authoring else None
            if script_rel:
                script_path = paths.content_path(script_rel)
                if not script_path.is_file() or _sha256(script_path) != source.get("script_sha256"):
                    problems.append("script hash is stale or missing")
            notes_path = paths.content_path(paths.lesson.content.notes)
            if not notes_path.is_file() or _sha256(notes_path) != source.get("notes_sha256"):
                problems.append("notes hash is stale or missing")
            pages = meta.get("pages") or []
            for previous, current in zip(pages, pages[1:]):
                if abs(float(current.get("start_s", 0)) - float(previous.get("end_s", 0))) > 0.01:
                    problems.append("page spans are not contiguous")
                    break
            for segment in meta.get("segments") or []:
                rel = segment.get("raw_wav")
                if rel and not (build_root / rel).is_file():
                    problems.append(f"segment file missing: {rel}")
            checks.append(
                _check(
                    "V-30",
                    not problems,
                    "narration meta, hashes, page spans and timeline are consistent",
                    "ok" if not problems else "; ".join(problems[:6]),
                )
            )
    else:
        checks.append(
            CheckRecord(id="V-30", status=Status.NOT_APPLICABLE, detail="narration disabled")
        )

    if paths.lesson.subtitles.enabled:
        from course_control.voice.subtitles import BilingualDraft, validate_cues

        problems: list[str] = []
        total_ms = int(shots_file.timeline.total_duration_s * 1000)
        policy = CuePolicy()
        bilingual = paths.lesson.subtitles.bilingual
        if paths.lesson.subtitles.render == "burn_in":
            draft_path = build_root / "subtitles" / "bilingual.draft.json"
            if not draft_path.is_file():
                problems.append(f"missing bilingual draft: {draft_path.name}")
            else:
                try:
                    draft = BilingualDraft.model_validate(
                        json.loads(draft_path.read_text(encoding="utf-8"))
                    )
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"cannot read draft: {exc}")
                    draft = None
                if draft is not None:
                    problems.extend(
                        validate_cues(
                            [cue.model_dump(mode="json") for cue in draft.cues],
                            policy,
                            float(fps or 30),
                            total_ms,
                        )
                    )
                    srt_path = build_root / "subtitles.srt"
                    if not srt_path.is_file():
                        problems.append("built subtitles.srt missing")
                    else:
                        actual = count_srt_cues(srt_path)
                        if actual != len(draft.cues):
                            problems.append(
                                f"SRT has {actual} cues but draft has {len(draft.cues)}"
                            )
        else:
            srt_path = paths.subtitles_path()
            if srt_path is None or not srt_path.is_file():
                problems.append("subtitle SRT missing")
            else:
                from course_control.quality.media_qc import _parse_srt

                cues = _parse_srt(srt_path.read_text(encoding="utf-8", errors="replace"))
                for position, cue in enumerate(cues, start=1):
                    duration = (cue["end_ms"] - cue["start_ms"]) / 1000.0
                    if duration < policy.min_seconds - 0.05:
                        problems.append(
                            f"cue {position}: duration {duration:.2f}s < {policy.min_seconds}s"
                        )
                    if duration > policy.max_seconds + 0.05:
                        problems.append(
                            f"cue {position}: duration {duration:.2f}s > {policy.max_seconds}s"
                        )
                    lines = [line for line in str(cue["text"]).splitlines() if line.strip()]
                    en = [line for line in lines if not re.search(r"[一-鿿]", line)]
                    zh = [line for line in lines if re.search(r"[一-鿿]", line)]
                    if bilingual and not en:
                        problems.append(f"cue {position}: missing top-language line")
                    if bilingual and not zh:
                        problems.append(f"cue {position}: missing bottom-language line")
                    if len(en) > policy.max_lines or len(zh) > policy.max_lines:
                        problems.append(f"cue {position}: too many lines")
                    for line in en:
                        if len(line) > policy.en_max_chars_per_line:
                            problems.append(
                                f"cue {position}: English line {len(line)} chars"
                            )
                    for line in zh:
                        if display_width(line) > policy.zh_max_chars_per_line:
                            problems.append(
                                f"cue {position}: Chinese line width {display_width(line):.1f}"
                            )
                    zh_chars = len(re.sub(r"\s", "", "".join(zh)))
                    if duration > 0 and zh_chars / duration > policy.zh_cps_max:
                        problems.append(
                            f"cue {position}: Chinese {zh_chars / duration:.1f} CPS > {policy.zh_cps_max}"
                        )
        checks.append(
            _check(
                "V-31",
                not problems,
                "subtitles are complete and within policy",
                "ok" if not problems else "; ".join(problems[:6]),
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-31", status=Status.NOT_APPLICABLE, detail="subtitles disabled")
        )

    if paths.lesson.subtitles.enabled:
        from course_control.voice.subtitles_qc import check_srt

        qc_path = (
            build_root / "subtitles.srt"
            if paths.lesson.subtitles.render == "burn_in"
            else paths.subtitles_path()
        )
        if qc_path is not None and qc_path.is_file():
            glossary = paths.lesson_dir / "authoring" / "glossary.yaml"
            qc = check_srt(
                qc_path,
                bilingual=paths.lesson.subtitles.bilingual,
                glossary_path=glossary,
            )
            detail = "ok" if qc["status"] == "PASS" else "; ".join(
                (qc["errors"] or qc["warnings"])[:6]
            )
            checks.append(
                _check(
                    "V-44",
                    qc["status"] != "FAIL",
                    "subtitle QC: timing, language, line breaks, glossary",
                    f"{qc['status']} ({qc['cues']} cues)" + ("" if qc["status"] == "PASS" else f": {detail}"),
                )
            )
        else:
            checks.append(
                CheckRecord(id="V-44", status=Status.NOT_APPLICABLE, detail="no subtitle file")
            )
    else:
        checks.append(
            CheckRecord(id="V-44", status=Status.NOT_APPLICABLE, detail="subtitles disabled")
        )

    if paths.lesson.narration.enabled:
        audio_ok = final_info.has_audio and abs(
            (final_info.audio_duration or 0.0) - (final_info.duration or 0.0)
        ) <= 0.5
        checks.append(
            _check(
                "V-15",
                audio_ok,
                "audio stream present; audio/video duration delta <= 0.5s",
                f"audio={final_info.has_audio}, delta={(final_info.audio_duration or 0) - (final_info.duration or 0):.3f}s",
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-15", status=Status.NOT_APPLICABLE, detail="narration disabled")
        )

    if paths.lesson.subtitles.enabled:
        subtitles = shots_file.subtitles or {}
        if str(subtitles.get("mode") or "cue") == "word":
            words_path = build_root / str(subtitles.get("words", ""))
            count = int(subtitles.get("words_count", 0))
            checks.append(
                _check(
                    "V-16",
                    words_path.is_file() and count > 0,
                    "word caption file exists and has words",
                    f"file={words_path.is_file()}, words={count}",
                )
            )
        else:
            subtitle_path = build_root / str(subtitles.get("path", ""))
            cues = int(subtitles.get("cues", 0))
            checks.append(
                _check(
                    "V-16",
                    subtitle_path.is_file() and cues > 0,
                    "subtitle file exists and has cues",
                    f"file={subtitle_path.is_file()}, cues={cues}",
                )
            )
    else:
        checks.append(
            CheckRecord(id="V-16", status=Status.NOT_APPLICABLE, detail="subtitles disabled")
        )

    if paths.lesson.compose.mode == "recording":
        notes_path = paths.content_path(paths.lesson.content.notes)
        notes_total = sum(page_budgets(notes_path.read_text(encoding="utf-8")))
        base = next((shot for shot in shots_file.shots if shot.kind == "recording"), None)
        actual = base.duration_s if base else 0.0
        checks.append(
            _check(
                "V-20",
                abs(actual - notes_total) <= tolerance,
                f"recording duration {notes_total:.3f} ± {tolerance}s",
                f"{actual:.3f}s",
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-20", status=Status.NOT_APPLICABLE, detail="deck mode")
        )

    annotations = shots_file.annotations
    if annotations:
        annotation_errors = []
        total = shots_file.timeline.total_duration_s
        for annotation in annotations:
            if annotation.kind == "text":
                if not annotation.text.strip():
                    annotation_errors.append(f"{annotation.id}: blank text")
            else:
                if annotation.max_value <= annotation.min_value:
                    annotation_errors.append(f"{annotation.id}: invalid legend range")
                if not annotation.stops:
                    annotation_errors.append(f"{annotation.id}: empty colormap stops")
                if not annotation.units.strip():
                    annotation_errors.append(f"{annotation.id}: blank legend units")
            if annotation.start_s + annotation.duration_s > total + 0.01:
                annotation_errors.append(f"{annotation.id}: ends after timeline")
            if any(
                component < 0.0 or component > 1.0 for component in annotation.position
            ):
                annotation_errors.append(f"{annotation.id}: position outside 0..1")
        checks.append(
            _check(
                "V-22",
                not annotation_errors,
                "annotations fit timeline; text and position valid",
                "ok" if not annotation_errors else "; ".join(annotation_errors),
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-22", status=Status.NOT_APPLICABLE, detail="no annotations")
        )

    timeline_path = build_root / "contracts" / "timeline.spec.json"
    if timeline_path.is_file():
        try:
            timeline_payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            checks.append(
                _check(
                    "V-43",
                    False,
                    "timeline.spec.json legacy fields are registered",
                    f"unreadable: {exc}",
                )
            )
        else:
            from course_control.content.legacy_registry import problems as legacy_problems

            issues = legacy_problems(timeline_payload)
            checks.append(
                _check(
                    "V-43",
                    not issues,
                    "timeline.spec.json legacy fields are registered with an exit plan",
                    "ok" if not issues else "; ".join(issues[:6]),
                )
            )
    else:
        checks.append(
            CheckRecord(
                id="V-43",
                status=Status.NOT_APPLICABLE,
                detail="timeline.spec.json missing",
            )
        )

    checks.append(_brand_check(paths, build_root))
    return checks
