"""One release check that chains the existing quality artifacts.

The check answers one question: can this version be published?  It does not add
style, ratio or duration gates.  It only makes the existing delivery checks run
in order and refuses to call a missing check a pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from course_control.content.paths import LessonPaths

PASS = "pass"
PASS_WITH_EXEMPTION = "pass_with_exemption"
FAIL = "fail"
INCOMPLETE = "incomplete"
EXEMPT = "exempt"


@dataclass
class Step:
    id: str
    status: str
    detail: str = ""
    report: str | None = None
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "detail": self.detail,
            "report": self.report,
            "data": self.data,
        }


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _overall(steps: list[Step]) -> str:
    if any(step.status == FAIL for step in steps):
        return FAIL
    if any(step.status == INCOMPLETE for step in steps):
        return INCOMPLETE
    if any(step.status == EXEMPT for step in steps):
        return PASS_WITH_EXEMPTION
    return PASS


def _stale_reason(paths: LessonPaths, video: Path) -> str | None:
    """The final video must match the inputs it claims to encode.

    Content hashes from build/<slug>/manifest.json decide when it exists;
    mtimes are only the documented fallback for a build that predates it.
    """
    from course_control.release.build_manifest import check_freshness

    freshness = check_freshness(paths, video)
    return None if freshness.fresh else (freshness.reason or "stale")


def _final_video(paths: LessonPaths) -> Path | None:
    final = paths.build_root / "final"
    for name in (
        "course-video-mixed.mp4",
        "course-video-captioned.mp4",
        "course-video.mp4",
    ):
        candidate = final / name
        if candidate.is_file():
            return candidate
    # A package that has already moved to deliver/ is still the film under
    # review; the build directory is allowed to be cleaned.
    for candidate in (
        paths.delivery_root / "final" / "master.mp4",
        paths.delivery_root / "final" / "captioned.mp4",
        paths.delivery_root / "master.mp4",
        paths.delivery_root / "final" / "course-video.mp4",
    ):
        if candidate.is_file():
            return candidate
    return None


def content_exception_for(build_root: Path, lesson: str) -> dict | None:
    """Return the blocking content exception for this lesson, if any.

    The per-lesson queue is authoritative; the shared file is an index and a
    legacy import.  A malformed queue or index is itself a blocking exception
    (see ``course_control.quality.exceptions``), never "no exception".
    """
    from course_control.quality.exceptions import blocking_exception

    return blocking_exception(build_root, lesson)


def _quality_inputs(paths: LessonPaths) -> dict:
    from course_control.quality.evidence import file_sha256

    content = getattr(paths.lesson, "content", None)
    return {
        "slides": file_sha256(paths.lesson_dir / content.slides) if content else None,
        "notes": file_sha256(paths.lesson_dir / content.notes) if content else None,
        "episode_spec": file_sha256(paths.lesson_dir / "authoring" / "episode.spec.yaml"),
    }


def _product_steps(paths: LessonPaths) -> list[Step]:
    """Product tier and visual-event checks, only for lessons that opted in.

    Legacy lessons stay exactly as they were: adding a step that says "not
    declared" would either block 20 existing courses or fake a pass.  A lesson
    that declares ``product_tier`` opts into both checks, and a missing plan is
    INCOMPLETE, never a pass.
    """
    from course_control.production.episode_spec import EpisodeSpecError, load_episode_spec
    from course_control.production.product import check_product
    from course_control.production.visual_events import (
        VisualEventError,
        load_plan,
        validate_plan,
    )

    tier = getattr(paths.lesson, "product_tier", None)
    plan_path = paths.build_root / "contracts" / "visual-events.json"
    if not tier and not plan_path.is_file():
        return []

    steps: list[Step] = []
    if tier:
        result = check_product(paths.lesson, paths.lesson_dir)
        status = PASS if result.status == "PASS" else FAIL if result.status == "FAIL" else INCOMPLETE
        steps.append(
            Step(
                "product_tier",
                status,
                f"{result.status}: " + (", ".join(result.errors or result.warnings) or "window, aspect and modules verified"),
                str(paths.build_root / "product.json"),
            )
        )

    episode = None
    spec_path = paths.lesson_dir / "authoring" / "episode.spec.yaml"
    if spec_path.is_file():
        try:
            episode = load_episode_spec(spec_path)
        except EpisodeSpecError as exc:
            steps.append(Step("visual_events", INCOMPLETE, f"episode spec: {exc}"))
            return steps

    if not plan_path.is_file():
        steps.append(
            Step("visual_events", INCOMPLETE, f"missing {plan_path}; run visual-events")
        )
        return steps
    try:
        report = validate_plan(load_plan(plan_path), build_root=paths.build_root, episode=episode)
    except VisualEventError as exc:
        steps.append(Step("visual_events", INCOMPLETE, str(exc)))
        return steps
    status = PASS if report.status == "PASS" else FAIL if report.status == "FAIL" else INCOMPLETE
    detail = "; ".join(report.errors or report.warnings) or f"{len(report.plan.events)} events verified"
    steps.append(Step("visual_events", status, detail, str(plan_path)))
    return steps


def _brand_steps(paths: LessonPaths) -> list[Step]:
    """Branded lessons must carry a complete token-frame proof.

    Unbranded lessons get no step.  A branded lesson with a missing or
    malformed report is INCOMPLETE; a report whose frames, rows or input
    hashes no longer match is FAIL.  The verifier never trusts a bare
    ``status: PASS``.
    """
    branding = getattr(paths.lesson, "branding", None)
    if branding is None or not getattr(branding, "enabled", False):
        return []

    from course_control.rendering.token_frames import (
        TokenFrameError,
        load_layout,
        load_tokens,
        verify_report,
    )

    report_path = paths.build_root / "brand" / "token-frames" / "report.json"
    if not report_path.is_file():
        return [
            Step(
                "brand_evidence",
                INCOMPLETE,
                f"branding enabled but {report_path} is missing; run token-frames-check",
            )
        ]
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [Step("brand_evidence", INCOMPLETE, f"cannot read brand evidence: {exc}")]

    workspace = getattr(paths, "workspace", None)
    if workspace is None:
        return [Step("brand_evidence", INCOMPLETE, "workspace is not available")]
    layout_path = Path(workspace) / "shared" / "design-tokens" / "swatch-layout.json"
    tokens_path = Path(workspace) / "shared" / "design-tokens" / "tokens.json"
    try:
        layout = load_layout(layout_path)
        tokens = load_tokens(tokens_path)
    except TokenFrameError as exc:
        return [Step("brand_evidence", INCOMPLETE, f"cannot read brand inputs: {exc}")]

    result = verify_report(
        report,
        layout=layout,
        tokens=tokens,
        layout_path=layout_path,
        tokens_path=tokens_path,
        report_path=report_path,
    )
    status = {"PASS": PASS, "FAIL": FAIL, "INCOMPLETE": INCOMPLETE}[result["status"]]
    detail = "; ".join(result["problems"]) or "token-frame proof verified"
    return [Step("brand_evidence", status, detail, str(report_path))]


def _lesson_steps(workspace: Path, paths: LessonPaths) -> list[Step]:
    from course_control.quality.certificate import issue, save as save_certificate
    from course_control.quality.defect import collect as collect_defects
    from course_control.quality.defect import save as save_defects
    from course_control.quality.media_qc import run_media_qc
    from course_control.quality.quality import build_quality_report
    from course_control.quality.quality_gates import evaluate
    from course_control.voice.subtitles_qc import check_srt

    steps: list[Step] = []
    exception = content_exception_for(paths.build_root, paths.slug)
    if exception is not None:
        steps.append(
            Step(
                "content_exception",
                INCOMPLETE,
                str(exception.get("reason") or exception.get("detail") or "open content exception"),
                data=exception,
            )
        )
        owner = str(exception.get("owner") or "").strip()
        if owner.lower() in {"", "unassigned", "tbd", "todo", "owner"}:
            steps.append(
                Step(
                    "content_exception_owner",
                    FAIL,
                    f"open content exception has no named owner: {owner or '<empty>'}",
                    data=exception,
                )
            )
    try:
        from course_control.authoring.pipeline import assert_storyboard_signed

        assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
        steps.append(Step("storyboard_signoff", PASS, "signed against the current storyboard"))
    except Exception as exc:  # noqa: BLE001 - missing evidence is INCOMPLETE
        steps.append(Step("storyboard_signoff", INCOMPLETE, str(exc)))

    video = _final_video(paths)
    if video is None:
        steps.append(
            Step("final_video", INCOMPLETE, "no final/course-video*.mp4; build first")
        )
        return steps
    from course_control.release.build_manifest import check_freshness

    freshness = check_freshness(paths, video)
    if not freshness.fresh:
        steps.append(
            Step(
                "final_video",
                FAIL,
                freshness.reason or "stale",
                data={"stale_by": freshness.stale_by, "build_id": freshness.build_id},
            )
        )
        return steps
    steps.append(
        Step(
            "final_video",
            PASS,
            f"{video} [stale_by: {freshness.stale_by}]",
            data={"stale_by": freshness.stale_by, "build_id": freshness.build_id},
        )
    )

    media, media_path = run_media_qc(workspace, paths, video_path=video)
    media_status = PASS if media.get("status") in {"PASS", "WARN"} else (
        FAIL if media.get("status") == "BLOCKED" else INCOMPLETE
    )
    steps.append(
        Step(
            "media_qc",
            media_status,
            f"{len(media.get('checks') or [])} checks, status={media.get('status')}",
            str(media_path),
        )
    )

    if paths.lesson.subtitles.enabled:
        subtitle = paths.subtitles_path()
        if subtitle is None or not subtitle.is_file():
            steps.append(Step("subtitles_qc", INCOMPLETE, "subtitles enabled but SRT missing"))
        else:
            report = check_srt(
                subtitle,
                bilingual=paths.lesson.subtitles.bilingual,
                glossary_path=paths.lesson_dir / "authoring" / "glossary.yaml",
            )
            from course_control.platform.media import sha256_file

            report["source"] = {"path": str(subtitle), "sha256": sha256_file(subtitle)}
            target = paths.build_root / "quality" / "subtitles-qc.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            status = PASS if report.get("status") in {"PASS", "WARN"} else FAIL
            steps.append(
                Step(
                    "subtitles_qc",
                    status,
                    f"{report.get('status')} · {report.get('cues', 0)} cues",
                    str(target),
                )
            )
    else:
        steps.append(Step("subtitles_qc", PASS, "subtitles disabled; not applicable"))

    # Burned subtitles are invisible to frame-audit, which reads the Remotion
    # composition. The ASS itself is the only place to prove the subtitle band
    # does not sit on a footer or a conclusion line.
    if paths.lesson.subtitles.enabled and paths.lesson.subtitles.render == "burn_in":
        from course_control.platform.media import sha256_file
        from course_control.voice.subtitle_bands import BandError, check_ass_band

        ass = paths.build_root / "subtitles.ass"
        target = paths.build_root / "quality" / "subtitle-bands.json"
        if not ass.is_file():
            steps.append(Step("subtitle_bands", INCOMPLETE, f"ASS missing: {ass}"))
        else:
            try:
                report = check_ass_band(
                    ass, workspace / "shared" / "design-tokens" / "episode-bands.yaml"
                )
            except BandError as exc:
                report = {"status": "FAIL", "detail": str(exc), "violations": []}
            report["source"] = {"path": str(ass), "sha256": sha256_file(ass)}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            steps.append(
                Step(
                    "subtitle_bands",
                    PASS if report.get("status") == "PASS" else FAIL,
                    str(report.get("detail") or ""),
                    str(target),
                    data={"violations": report.get("violations") or []},
                )
            )
    else:
        steps.append(Step("subtitle_bands", PASS, "subtitles not burned in; not applicable"))

    quality, quality_path = build_quality_report(workspace, paths)
    quality_status = PASS
    for item in quality.get("dimensions") or []:
        status = item.get("status")
        reason = str(item.get("reason") or "")
        if status == "BLOCKED":
            # Missing artifacts are missing evidence, not a quality verdict.
            if reason.startswith("missing release artifacts"):
                if quality_status != FAIL:
                    quality_status = INCOMPLETE
            else:
                quality_status = FAIL
        elif status == "INCOMPLETE" and quality_status != FAIL:
            quality_status = INCOMPLETE
    steps.append(
        Step(
            "quality_report",
            quality_status,
            f"{len(quality.get('dimensions') or [])} dimensions",
            str(quality_path),
        )
    )

    gate = evaluate(paths)
    gate_status = PASS if gate.get("verification_status") == "pass" else (
        FAIL if gate.get("verification_status") == "fail" else INCOMPLETE
    )
    steps.append(
        Step(
            "quality_gate",
            gate_status,
            f"{gate.get('verification_status')}",
            str(paths.build_root / "quality" / "gate.json"),
            data={
                "hard_failures": gate.get("hard_failures") or [],
                "incomplete": gate.get("incomplete") or [],
                "blocking_warnings": gate.get("blocking_warnings") or [],
            },
        )
    )

    quality_path = paths.build_root / "quality" / "quality-report.json"
    if quality_path.is_file():
        try:
            quality = json.loads(quality_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            quality = None
        if isinstance(quality, dict):
            recorded = quality.get("content_inputs")
            current = _quality_inputs(paths)
            if not isinstance(recorded, dict):
                steps.append(
                    Step(
                        "quality_freshness",
                        INCOMPLETE,
                        "quality report does not record the content it verified; re-run quality-report",
                    )
                )
            elif recorded != current:
                steps.append(
                    Step(
                        "quality_freshness",
                        INCOMPLETE,
                        "quality report predates the current slides/notes/spec; re-run quality-report",
                    )
                )
            else:
                steps.append(Step("quality_freshness", PASS, "quality report matches the current content"))

    defects = collect_defects(paths.build_root, paths.slug)
    defects_path = save_defects(defects, paths.build_root / "quality" / "defects.json")
    open_defects = [
        item for item in defects.defects if str(item.status) in {"open", "repairing"}
    ]
    steps.append(
        Step(
            "defects",
            FAIL if open_defects else PASS,
            f"{len(open_defects)} open / {len(defects.defects)} total",
            str(defects_path),
        )
    )

    steps.extend(_product_steps(paths))
    steps.extend(_brand_steps(paths))

    blocking = [
        step.id for step in steps if step.status not in {PASS, PASS_WITH_EXEMPTION}
    ]
    certificate = issue(paths.build_root, paths.slug, blocking=blocking)
    certificate_path = save_certificate(
        certificate, paths.build_root / "quality" / "certificate.json"
    )
    certificate_status = (
        PASS if certificate.verdict == "pass" else
        FAIL if certificate.verdict == "fail" else INCOMPLETE
    )
    steps.append(
        Step(
            "certificate",
            certificate_status,
            certificate.reason or certificate.verdict,
            str(certificate_path),
        )
    )
    return steps


def _topic_steps(
    workspace: Path, video: Path, licences: list[dict] | None = None
) -> list[Step]:
    """Delivery checks for a topic film; no lesson-only reports are invented."""
    from course_control.quality.media_qc import _measure_loudness, detect_black_freeze
    from course_control.platform.utils import probe_media, run_command, which_command

    steps: list[Step] = []
    if not video.is_file():
        steps.append(Step("final_video", INCOMPLETE, f"missing: {video}"))
        return steps
    if licences is None:
        steps.append(Step("licences", INCOMPLETE, "no licence declaration"))
    elif not licences:
        steps.append(Step("licences", PASS, "no third-party assets declared"))
    else:
        unknown = [item for item in licences if item.get("status") == "unknown"]
        missing_attr = [
            item
            for item in licences
            if item.get("status") == "cc_by" and not (item.get("attribution") or "").strip()
        ]
        bad = unknown + missing_attr
        steps.append(
            Step(
                "licences",
                FAIL if bad else PASS,
                f"{len(licences) - len(bad)}/{len(licences)} clear",
                data={"unclear": bad},
            )
        )
    steps.append(Step("final_video", PASS, str(video)))
    info = probe_media(video)
    steps.append(
        Step(
            "media_probe",
            PASS if info.duration and info.width and info.height else FAIL,
            f"{info.width}x{info.height} {info.duration:.2f}s audio={info.has_audio}",
            data=info.as_dict(),
        )
    )
    decode = run_command(
        [*which_command("ffmpeg"), "-v", "error", "-i", str(video), "-f", "null", "-"],
        workspace,
        timeout=1800,
    )
    steps.append(
        Step(
            "decode",
            PASS if decode.exit_code == 0 and not decode.stderr.strip() else FAIL,
            decode.stderr[-800:] or "full decode ok",
        )
    )
    if info.has_audio:
        loudness = _measure_loudness(video, workspace)
        steps.append(
            Step(
                "loudness",
                PASS if loudness.get("integrated_lufs") is not None else INCOMPLETE,
                f"{loudness.get('integrated_lufs')} LUFS / {loudness.get('true_peak_dbfs')} dBTP",
                data=loudness,
            )
        )
    else:
        steps.append(Step("loudness", INCOMPLETE, "no audio stream"))
    black, freeze = detect_black_freeze(
        video, workspace, video.parent / "media-qc-blackfreeze.log"
    )
    steps.append(
        Step(
            "black",
            PASS if not black else FAIL,
            f"{len(black)} black interval(s)",
            data={"intervals": black[:20]},
        )
    )
    steps.append(
        Step(
            "freeze",
            PASS,
            f"{len(freeze)} frozen interval(s); review intentional holds",
            data={"intervals": freeze[:20]},
        )
    )
    return steps


_EXEMPTION_FIELDS = ("object", "reason", "operator", "time", "missing_checks", "delivery_version")


def _valid_exemption(path: Path) -> tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, "exemption is not an object"
    missing = [key for key in _EXEMPTION_FIELDS if not data.get(key)]
    if missing:
        return False, "missing fields: " + ", ".join(missing)
    return True, ""


def _shot_review_steps(workspace: Path, shot_review_dir: Path) -> list[Step]:
    directory = Path(shot_review_dir)
    if not directory.is_dir():
        return [Step("shot_review", INCOMPLETE, f"review directory missing: {directory}")]
    packages = sorted(
        item for item in directory.iterdir()
        if item.is_dir() and ((item / "qc.json").is_file() or (item / "exemption.json").is_file())
    )
    if not packages:
        return [Step("shot_review", INCOMPLETE, f"no review packages under {directory}")]
    shots: list[dict] = []
    status = PASS
    exempt = False
    for package in packages:
        shot = package.name
        qc_path = package / "qc.json"
        exemption = package / "exemption.json"
        valid_exemption, exemption_detail = (False, "")
        if exemption.is_file():
            valid_exemption, exemption_detail = _valid_exemption(exemption)
        if not qc_path.is_file():
            if valid_exemption:
                shots.append({"shot": shot, "status": EXEMPT,
                              "detail": exemption_detail or "recorded exemption"})
                exempt = True
            else:
                shots.append({"shot": shot, "status": INCOMPLETE,
                              "detail": "review missing; no valid exemption"})
                status = INCOMPLETE if status != FAIL else status
            continue
        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            shots.append({"shot": shot, "status": INCOMPLETE, "detail": str(exc)})
            status = INCOMPLETE if status != FAIL else status
            continue
        qc_status = str(qc.get("status") or INCOMPLETE).upper()
        if qc_status == "FAIL":
            shots.append({"shot": shot, "status": FAIL, "detail": "review QC failed"})
            status = FAIL
        elif qc_status in {"PASS", "WARN"}:
            detail = "review passed" if qc_status == "PASS" else "review passed with warnings"
            shots.append({"shot": shot, "status": PASS, "detail": detail})
        elif valid_exemption:
            shots.append({"shot": shot, "status": EXEMPT,
                          "detail": exemption_detail or "recorded exemption"})
            exempt = True
        elif exemption.is_file():
            shots.append({"shot": shot, "status": INCOMPLETE,
                          "detail": f"invalid exemption: {exemption_detail}"})
            status = INCOMPLETE if status != FAIL else status
        else:
            shots.append({"shot": shot, "status": INCOMPLETE,
                          "detail": "review incomplete; no exemption"})
            status = INCOMPLETE if status != FAIL else status
    if status == FAIL:
        final = FAIL
    elif status == INCOMPLETE:
        final = INCOMPLETE
    elif exempt:
        final = EXEMPT
    else:
        final = PASS
    return [Step(
        "shot_review",
        final,
        f"{len(packages)} package(s); {sum(1 for item in shots if item['status'] == EXEMPT)} exemption(s)",
        str(directory),
        data={"shots": shots},
    )]


def _lesson_approval_problems(paths: LessonPaths) -> list[str]:
    """The human gate, checked against the files it approves."""
    from course_control.quality.evidence import evidence_problems

    return evidence_problems(
        lesson=paths.slug,
        review_path=paths.build_root / "quality" / "review-approval.json",
        release_path=paths.build_root / "quality" / "release-approval.json",
        build_report=paths.build_root / "final" / "build-report.json",
        final_video=_final_video(paths),
        quality_report=paths.build_root / "quality" / "quality-report.json",
        require_release=True,
    )


def run_release_check(
    workspace: Path,
    *,
    paths: LessonPaths | None = None,
    topic_video: Path | None = None,
    licences: list[dict] | None = None,
    shot_review_dir: Path | None = None,
) -> dict:
    approvals: list[str] = []
    if paths is not None:
        steps = _lesson_steps(workspace.resolve(), paths)
        subject = {"kind": "lesson", "id": paths.slug}
        approvals = _lesson_approval_problems(paths)
    elif topic_video is not None:
        steps = _topic_steps(workspace.resolve(), topic_video, licences)
        subject = {"kind": "topic_video", "id": topic_video.stem}
    else:
        raise ValueError("release-check needs a lesson or a topic video")
    if shot_review_dir is not None:
        steps.extend(_shot_review_steps(workspace.resolve(), shot_review_dir))
    status = _overall(steps)
    return {
        "schema_version": 1,
        "kind": "release_check",
        "generated_at": _now(),
        "subject": subject,
        "status": status,
        "steps": [step.as_dict() for step in steps],
        "approval_problems": approvals,
        # A pass status only says the automatic checks ran.  Delivery also
        # needs both human approvals, bound to this build and film.
        "delivery_allowed": status in {PASS, PASS_WITH_EXEMPTION} and not approvals,
    }


__all__ = ["FAIL", "INCOMPLETE", "PASS", "PASS_WITH_EXEMPTION", "Step", "run_release_check"]
