"""Preview and release rendering for a topic project.

A topic film is not a lesson: it may have no slides, no storyboard and no
narration contract.  It still gets the same units, the same cache and the same
preview/release split.  The film is a Remotion composition declared in
``project.yaml``; ``shots`` and ``segments`` only define review boundaries.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from course_control.delivery.project import ProjectSpec, TopicSegment
from course_control.preview.profile import PreviewLevel, PreviewProfile, RenderMode
from course_control.preview.remotion_window import render_window
from course_control.preview.units import PreviewUnit
from course_control.platform.workspace_layout import build_root_for, content_root, delivery_root_for, projects_root


@dataclass
class TopicContext:
    spec: ProjectSpec
    workspace: Path
    project_dir: Path
    build_root: Path
    entry: str
    composition: str
    output_name: str
    delivery_dir: Path
    props: Path | None
    width: int
    height: int
    fps: int

    @property
    def project_id(self) -> str:
        return self.spec.project.id

    @property
    def plan(self):
        return self.spec.production.topic_video


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_topic(workspace: Path, project_file: Path) -> TopicContext:
    from course_control.delivery.project import load_project

    spec = load_project(project_file)
    if spec.project.mode != "topic_video":
        raise ValueError(f"{project_file} is mode={spec.project.mode!r}, not topic_video")
    plan = spec.production.topic_video
    if plan is None:
        raise ValueError("topic_video requires production.topic_video")
    width_s, height_s = spec.media.resolution.lower().split("x", 1)
    project_dir = Path(project_file).resolve().parent
    props = (project_dir / plan.props).resolve() if plan.props else None
    if plan.delivery_dir:
        delivery = (content_root(workspace) / plan.delivery_dir).resolve()
    else:
        delivery = delivery_root_for(workspace.resolve(), spec.project.id)
    return TopicContext(
        spec=spec,
        workspace=workspace.resolve(),
        project_dir=project_dir,
        build_root=build_root_for(workspace, spec.project.id),
        entry=plan.entry or "",
        composition=plan.composition or "",
        output_name=plan.output or f"{spec.project.id}.mp4",
        delivery_dir=delivery,
        props=props,
        width=int(width_s),
        height=int(height_s),
        fps=spec.media.frame_rate,
    )


def _units_from(context: TopicContext, level: PreviewLevel) -> list[PreviewUnit]:
    plan = context.plan
    shots: list[TopicSegment] = list(plan.shots or [])
    segments: list[TopicSegment] = list(plan.segments or [])
    if level is PreviewLevel.PROJECT:
        shots = []
        segments = []
        return [
            PreviewUnit(
                id="project",
                kind="remotion",
                start_s=0.0,
                end_s=float(plan.target_seconds),
                segment="project",
                label="project",
                composition=context.composition,
                entry=context.entry,
            )
        ]
    if level is PreviewLevel.SEGMENT and segments:
        return [
            PreviewUnit(
                id=item.id,
                kind="remotion",
                start_s=item.start_s,
                end_s=item.end_s,
                segment=item.id,
                label=item.label or "segment",
                composition=context.composition,
                entry=context.entry,
            )
            for item in segments
        ]
    if shots:
        return [
            PreviewUnit(
                id=item.id,
                kind="remotion",
                start_s=item.start_s,
                end_s=item.end_s,
                segment=item.segment or (segments[0].id if segments else "part-01"),
                label=item.label or "shot",
                composition=context.composition,
                entry=context.entry,
            )
            for item in shots
        ]
    # A monolithic film with no declared units still gets one unit per segment,
    # or the whole film if even segments are absent.
    if segments:
        return [
            PreviewUnit(
                id=item.id,
                kind="remotion",
                start_s=item.start_s,
                end_s=item.end_s,
                segment=item.id,
                label=item.label or "segment",
                composition=context.composition,
                entry=context.entry,
            )
            for item in segments
        ]
    return [
        PreviewUnit(
            id="project",
            kind="remotion",
            start_s=0.0,
            end_s=float(plan.target_seconds),
            segment="project",
            label="project",
            composition=context.composition,
            entry=context.entry,
        )
    ]


def _sync_public_assets(context: TopicContext) -> None:
    """Copy topic asset directories into Remotion's public folder.

    Remotion's bundler cannot follow Windows junctions in ``public/`` (it tries
    to recreate them as symlinks and gets EPERM), so the source stays in the
    content root and this function makes a real staging copy before rendering.
    """
    assets = context.plan.public_assets if context.plan is not None else []
    if not assets:
        return
    public = context.workspace / "RemotionStudio" / "public"
    for item in assets:
        source = Path(item.source)
        if not source.is_absolute():
            source = (context.project_dir / source).resolve()
        if not source.is_dir():
            raise ValueError(f"public asset source not found: {source}")
        target = public / item.name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)


def run_topic_preview(
    context: TopicContext,
    *,
    level: PreviewLevel | str,
    profile: PreviewProfile,
    selection: set[str] | None = None,
    force: bool = False,
) -> dict:
    level = PreviewLevel(level)
    _sync_public_assets(context)
    if not context.entry or not context.composition:
        raise ValueError(
            "topic preview requires production.topic_video.entry and .composition"
        )
    units = _units_from(context, level)
    if selection:
        units = [unit for unit in units if unit.id in selection or unit.segment in selection]
    if not units:
        raise ValueError("no topic preview units matched")
    started = time.monotonic()
    rows: list[dict] = []
    offset_frames = int(round(float(context.plan.offset_s) * profile.fps))
    for unit in units:
        result = render_window(
            unit_id=unit.id,
            workspace=context.workspace,
            remotion_root=context.workspace / "RemotionStudio",
            entry=context.entry,
            composition=context.composition,
            output=context.build_root / "preview" / level.value / f"{unit.id}.mp4",
            start_frame=offset_frames + unit.start_frame(profile.fps),
            end_frame=offset_frames + unit.end_frame(profile.fps),
            profile=profile,
            props=context.props,
            timeout_s=1800,
            log_path=context.build_root / "preview" / "logs" / f"{unit.id}.log",
            force=force,
        )
        rows.append(
            {
                "unit": result.unit_id,
                "status": result.status,
                "output": str(result.path) if result.path else None,
                "duration_ms": result.duration_ms,
                "key": result.key,
                "frames": result.frames,
                "warnings": result.warnings or [],
                "detail": result.detail,
                "start_s": unit.start_s,
                "end_s": unit.end_s,
                "segment": unit.segment,
            }
        )
    failed = [row for row in rows if row["status"] == "failed"]
    payload = {
        "schema_version": 1,
        "kind": "preview_report",
        "project": context.project_id,
        "mode": RenderMode.PREVIEW.value,
        "level": level.value,
        "generated_at": _now(),
        "profile": profile.as_dict(),
        "units": rows,
        "totals": {
            "units": len(rows),
            "ok": len(rows) - len(failed) - len([r for r in rows if r["status"] == "cached"]),
            "cached": len([r for r in rows if r["status"] == "cached"]),
            "failed": len(failed),
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
        "delivery_allowed": False,
        "ok": not failed,
    }
    target = context.build_root / "preview" / "report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["report"] = str(target)
    (context.build_root / "preview" / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def run_topic_pilot(
    context: TopicContext,
    *,
    profile: PreviewProfile,
    force: bool = False,
) -> dict:
    """Run P0, P1 and P2 for a topic project and record each level's cost."""
    levels = [PreviewLevel.SHOT, PreviewLevel.SEGMENT, PreviewLevel.PROJECT]
    results: dict[str, dict] = {}
    for level in levels:
        payload = run_topic_preview(
            context, level=level, profile=profile, force=force
        )
        report_path = Path(payload["report"])
        level_report = report_path.with_name(f"report-{level.value}.json")
        try:
            shutil.copyfile(report_path, level_report)
        except OSError:
            level_report = report_path
        results[level.value] = {
            "units": payload["totals"]["units"],
            "ok": payload["totals"]["ok"],
            "cached": payload["totals"]["cached"],
            "failed": payload["totals"]["failed"],
            "duration_ms": payload["totals"]["duration_ms"],
            "report": str(level_report),
        }
    summary = {
        "schema_version": 1,
        "kind": "preview_pilot",
        "project": context.project_id,
        "profile": profile.as_dict(),
        "levels": results,
        "generated_at": _now(),
    }
    target = context.build_root / "preview" / "pilot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    summary["report"] = str(target)
    return summary


def release_topic(context: TopicContext) -> dict:
    """Render to the build area, then install only after a bound approval."""
    import shutil

    from course_control.preview.profile import profile_for
    from course_control.platform.media import sha256_file

    _sync_public_assets(context)
    if not context.entry or not context.composition:
        raise ValueError(
            "topic release requires production.topic_video.entry and .composition"
        )

    profile = profile_for(
        RenderMode.RELEASE,
        PreviewLevel.PROJECT,
        width=context.width,
        height=context.height,
        fps=context.fps,
    )
    candidate_dir = context.build_root / "release"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / context.output_name
    result = render_window(
        unit_id="project",
        workspace=context.workspace,
        remotion_root=context.workspace / "RemotionStudio",
        entry=context.entry,
        composition=context.composition,
        output=candidate,
        start_frame=int(round(float(context.plan.offset_s) * context.fps)),
        end_frame=int(
            round(
                (float(context.plan.offset_s) + float(context.plan.target_seconds))
                * context.fps
            )
        ),
        profile=profile,
        props=context.props,
        timeout_s=3600,
        log_path=context.build_root / "logs" / "release.log",
    )
    if result.status not in {"ok", "cached"} or result.path is None or not result.path.is_file():
        return {
            "verdict": "fail",
            "output": str(result.path) if result.path else None,
            "status": result.status,
            "detail": result.detail,
            "installed": False,
        }

    output_sha = sha256_file(candidate)
    approval_path = candidate_dir / "approval.json"
    approval = None
    if approval_path.is_file():
        try:
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            approval = None
    from course_control.quality.evidence import is_named_approver

    approved = bool(
        approval
        and approval.get("decision") == "approved"
        and is_named_approver(approval.get("approved_by"))
        and approval.get("stage") == "release"
        and approval.get("output_sha256") == output_sha
        and str(approval.get("project") or "") == context.project_id
    )
    if not approved:
        return {
            "verdict": "incomplete",
            "output": str(candidate),
            "status": result.status,
            "detail": "release approval is missing or not bound to this output",
            "installed": False,
        }

    delivery = context.delivery_dir
    delivery.mkdir(parents=True, exist_ok=True)
    target = delivery / context.output_name
    staged = target.with_name(target.name + ".tmp")
    shutil.copy2(candidate, staged)
    staged.replace(target)
    manifest = {
        "schema_version": 1,
        "kind": "topic_delivery",
        "project": context.project_id,
        "mode": "topic_video",
        "composition": context.composition,
        "entry": context.entry,
        "generated_at": _now(),
        "resolution": [context.width, context.height],
        "fps": context.fps,
        "verdict": "pass",
        "approval": {
            "approved_by": approval.get("approved_by"),
            "approved_at": approval.get("approved_at"),
            "output_sha256": output_sha,
        },
        "files": [
            {
                "path": target.name,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        ],
    }
    (delivery / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10),
        encoding="utf-8",
    )
    return {
        "verdict": "pass",
        "output": str(target),
        "status": result.status,
        "detail": result.detail,
        "installed": True,
    }


__all__ = [
    "TopicContext",
    "load_topic",
    "release_topic",
    "run_topic_pilot",
    "run_topic_preview",
]
