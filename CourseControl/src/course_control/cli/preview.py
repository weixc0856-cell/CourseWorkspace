"""Preview and release rendering commands.

``preview`` changes the raster, never the design.  The same commands also run a
release render so a lesson and a topic film share one entry point.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import app
from course_control.cli._common import _paths

render_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Preview (480p) and release renders; release-check issues the verdict.",
)
app.add_typer(render_app, name="render")


def _require_signoff(paths) -> None:
    """The storyboard gate applies to every motion render of a lesson."""
    from course_control.authoring.pipeline import assert_storyboard_signed

    try:
        assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
    except Exception as exc:  # noqa: BLE001 - the gate is user-facing
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)


def _mode(value: str):
    from course_control.preview.profile import RenderMode

    try:
        return RenderMode(value)
    except ValueError:
        typer.echo("--mode must be preview or release", err=True)
        raise typer.Exit(2)


def _profile(paths, mode, level, short_edge: int):
    from course_control.preview.profile import profile_for

    width, height = paths.lesson.outputs.resolution
    return profile_for(
        mode,
        level,
        width=width,
        height=height,
        fps=int(paths.lesson.outputs.fps),
        audio=mode.value == "release" or level.value != "shot",
        short_edge=short_edge,
    )


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    typer.echo(f"level: {payload.get('level')}  mode: {payload.get('mode')}")
    for row in payload.get("units") or []:
        detail = f" — {row.get('detail')}" if row.get("detail") else ""
        typer.echo(f"  [{row.get('status')}] {row.get('unit')}{detail}")
    totals = payload.get("totals") or {}
    typer.echo(
        f"units: {totals.get('units', 0)}  ok: {totals.get('ok', 0)}  "
        f"cached: {totals.get('cached', 0)}  failed: {totals.get('failed', 0)}  "
        f"{totals.get('duration_ms', 0) / 1000:.1f}s"
    )
    for row in payload.get("units") or []:
        for warning in row.get("warnings") or []:
            typer.echo(f"  warning: {row.get('unit')}: {warning}")
    if payload.get("report"):
        typer.echo(f"report: {payload['report']}")
    typer.echo(f"ok: {payload.get('ok')}")


@render_app.command("shot")
def render_shot(
    lesson: str = typer.Option(..., "--lesson"),
    shot: list[str] = typer.Option(None, "--shot", help="Shot id; repeat for several"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    mode: str = typer.Option("preview", "--mode", help="preview or release"),
    short_edge: int = typer.Option(480, "--short-edge", help="Preview short edge in pixels"),
    force: bool = typer.Option(False, "--force", help="Ignore the preview cache"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Render one or more shots.  Preview is 480p; release is full size."""
    from course_control.preview.profile import PreviewLevel
    from course_control.preview.runner import run_preview

    render_mode = _mode(mode)
    try:
        paths = _paths(workspace, lesson, lesson_dir)
        _require_signoff(paths)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - contract errors are user-facing
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    profile = _profile(paths, render_mode, PreviewLevel.SHOT, short_edge)
    output_root = None
    if render_mode.value == "release":
        output_root = paths.build_root / "release" / "shot"
    try:
        payload = run_preview(
            paths,
            level=PreviewLevel.SHOT,
            profile=profile,
            selection=set(shot) if shot else None,
            force=force,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    _emit(payload, as_json)
    raise typer.Exit(0 if payload["ok"] else 1)


@render_app.command("segment")
def render_segment(
    lesson: str = typer.Option(..., "--lesson"),
    segment: list[str] = typer.Option(None, "--segment", help="Segment id; repeat for several"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    mode: str = typer.Option("preview", "--mode", help="preview or release"),
    short_edge: int = typer.Option(480, "--short-edge"),
    force: bool = typer.Option(False, "--force"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Render one or more segments as one Remotion window."""
    from course_control.preview.profile import PreviewLevel
    from course_control.preview.runner import run_preview

    render_mode = _mode(mode)
    try:
        paths = _paths(workspace, lesson, lesson_dir)
        _require_signoff(paths)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    profile = _profile(paths, render_mode, PreviewLevel.SEGMENT, short_edge)
    output_root = paths.build_root / "release" / "segment" if render_mode.value == "release" else None
    try:
        payload = run_preview(
            paths,
            level=PreviewLevel.SEGMENT,
            profile=profile,
            selection=set(segment) if segment else None,
            force=force,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    _emit(payload, as_json)
    raise typer.Exit(0 if payload["ok"] else 1)


@render_app.command("project")
def render_project(
    lesson: str = typer.Option(None, "--lesson"),
    project: Path = typer.Option(None, "--project", help="project.yaml for a topic video"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    mode: str = typer.Option("preview", "--mode", help="preview or release"),
    shot: list[str] = typer.Option(None, "--shot", help="Topic film shot id; repeat for several"),
    segment: list[str] = typer.Option(None, "--segment", help="Topic film segment id; repeat for several"),
    short_edge: int = typer.Option(480, "--short-edge"),
    force: bool = typer.Option(False, "--force"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Render the whole film.  ``--project`` handles a topic video."""
    from course_control.preview.profile import PreviewLevel
    from course_control.preview.runner import release_build, run_preview

    render_mode = _mode(mode)
    if bool(lesson) == bool(project):
        typer.echo("give exactly one of --lesson or --project", err=True)
        raise typer.Exit(2)

    if project is not None:
        from course_control.delivery.project import load_project
        from course_control.preview.topic import load_topic, release_topic, run_topic_preview
        from course_control.preview.profile import profile_for

        try:
            spec = load_project(project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        if spec.project.mode == "course":
            slug = (
                spec.production.course.lesson
                if spec.production.course is not None
                else None
            ) or spec.project.id
            try:
                paths = _paths(workspace, slug, lesson_dir)
            except Exception as exc:  # noqa: BLE001
                typer.echo(str(exc), err=True)
                raise typer.Exit(1)
            _require_signoff(paths)
            if render_mode.value == "release":
                payload = release_build(paths)
                if as_json:
                    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    typer.echo(f"verdict: {payload['verdict']}")
                    for stage in payload["stages"]:
                        typer.echo(f"  {stage['name']}: {stage['status']}")
                    for failure in payload["failures"]:
                        typer.echo(f"  ! {failure}")
                raise typer.Exit(1 if payload["verdict"] == "fail" else 0)
            profile = _profile(paths, render_mode, PreviewLevel.PROJECT, short_edge)
            try:
                payload = run_preview(
                    paths,
                    level=PreviewLevel.PROJECT,
                    profile=profile,
                    force=force,
                )
            except (OSError, ValueError) as exc:
                typer.echo(f"failed: {exc}", err=True)
                raise typer.Exit(1)
            _emit(payload, as_json)
            raise typer.Exit(0 if payload["ok"] else 1)

        try:
            context = load_topic(workspace.resolve(), project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        if render_mode.value == "release":
            result = release_topic(context)
            typer.echo(f"verdict: {result.get('verdict')}")
            typer.echo(f"output: {result.get('output')}")
            if result.get("detail"):
                typer.echo(f"detail: {result['detail']}", err=True)
            raise typer.Exit(0 if result.get("verdict") == "pass" else 1)
        level = PreviewLevel.PROJECT
        selection = None
        if shot:
            level = PreviewLevel.SHOT
            selection = set(shot)
        elif segment:
            level = PreviewLevel.SEGMENT
            selection = set(segment)
        profile = profile_for(
            render_mode,
            level,
            width=context.width,
            height=context.height,
            fps=context.fps,
        )
        try:
            payload = run_topic_preview(
                context,
                level=level,
                profile=profile,
                selection=selection,
                force=force,
            )
        except (OSError, ValueError) as exc:
            typer.echo(f"failed: {exc}", err=True)
            raise typer.Exit(1)
        _emit(payload, as_json)
        raise typer.Exit(0 if payload["ok"] else 1)

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    _require_signoff(paths)
    if render_mode.value == "release":
        payload = release_build(paths)
        if as_json:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            typer.echo(f"verdict: {payload['verdict']}")
            for stage in payload["stages"]:
                typer.echo(f"  {stage['name']}: {stage['status']}")
            for failure in payload["failures"]:
                typer.echo(f"  ! {failure}")
            typer.echo(f"report: {payload['report']}")
        raise typer.Exit(1 if payload["verdict"] == "fail" else 0)

    profile = _profile(paths, render_mode, PreviewLevel.PROJECT, short_edge)
    try:
        payload = run_preview(
            paths,
            level=PreviewLevel.PROJECT,
            profile=profile,
            force=force,
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    _emit(payload, as_json)
    raise typer.Exit(0 if payload["ok"] else 1)


@app.command("preview-pilot")
def preview_pilot(
    lesson: str | None = typer.Option(None, "--lesson"),
    project: Path | None = typer.Option(None, "--project", help="project.yaml for a topic video"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    short_edge: int = typer.Option(480, "--short-edge"),
    force: bool = typer.Option(False, "--force"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run P0, P1 and P2 for a lesson or topic project and record the cost."""
    from course_control.preview.profile import PreviewLevel, RenderMode
    from course_control.preview.runner import run_pilot

    if bool(lesson) == bool(project):
        typer.echo("give exactly one of --lesson or --project", err=True)
        raise typer.Exit(2)
    if project is not None:
        from course_control.preview.profile import profile_for
        from course_control.preview.topic import load_topic, run_topic_pilot

        try:
            context = load_topic(workspace.resolve(), project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        profile = profile_for(
            RenderMode.PREVIEW,
            PreviewLevel.SHOT,
            width=context.width,
            height=context.height,
            fps=context.fps,
            short_edge=short_edge,
        )
        try:
            payload = run_topic_pilot(context, profile=profile, force=force)
        except (OSError, ValueError) as exc:
            typer.echo(f"failed: {exc}", err=True)
            raise typer.Exit(1)
    else:
        try:
            paths = _paths(workspace, lesson, lesson_dir)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        _require_signoff(paths)
        profile = _profile(paths, RenderMode.PREVIEW, PreviewLevel.SHOT, short_edge)
        try:
            payload = run_pilot(paths, profile=profile, force=force)
        except (OSError, ValueError) as exc:
            typer.echo(f"failed: {exc}", err=True)
            raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for level, data in payload["levels"].items():
            typer.echo(
                f"{level}: {data['units']} units, {data['ok']} ok, "
                f"{data['cached']} cached, {data['failed']} failed, "
                f"{data['duration_ms'] / 1000:.1f}s"
            )
        typer.echo(f"report: {payload['report']}")
    failed = sum(item["failed"] for item in payload["levels"].values())
    raise typer.Exit(0 if not failed else 1)


@app.command("release-check")
def release_check(
    lesson: str = typer.Option(None, "--lesson"),
    project: Path = typer.Option(None, "--project", help="project.yaml for a topic video"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    shot_review_dir: Path | None = typer.Option(None, "--shot-review-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run the delivery checks in order and print PASS / FAIL / INCOMPLETE."""
    from course_control.release.check import INCOMPLETE, PASS, PASS_WITH_EXEMPTION, run_release_check

    if bool(lesson) == bool(project):
        typer.echo("give exactly one of --lesson or --project", err=True)
        raise typer.Exit(2)
    if lesson:
        try:
            paths = _paths(workspace, lesson, lesson_dir)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        payload = run_release_check(
            workspace.resolve(), paths=paths, shot_review_dir=shot_review_dir
        )
    else:
        from course_control.delivery.project import load_project
        from course_control.preview.topic import load_topic

        try:
            spec = load_project(project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        if spec.project.mode == "course":
            slug = (
                spec.production.course.lesson
                if spec.production.course is not None
                else None
            ) or spec.project.id
            try:
                paths = _paths(workspace, slug, lesson_dir)
            except Exception as exc:  # noqa: BLE001
                typer.echo(str(exc), err=True)
                raise typer.Exit(1)
            payload = run_release_check(
                workspace.resolve(), paths=paths, shot_review_dir=shot_review_dir
            )
            if as_json:
                typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                typer.echo(f"status: {payload['status']}")
                for step in payload["steps"]:
                    typer.echo(f"  [{step['status']}] {step['id']}: {step['detail']}")
            raise typer.Exit(
                0 if payload["status"] in {PASS, PASS_WITH_EXEMPTION}
                else (3 if payload["status"] == INCOMPLETE else 1)
            )
        try:
            context = load_topic(workspace.resolve(), project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        video = context.delivery_dir / context.output_name
        licences = [item.model_dump(mode="json") for item in context.plan.licences]
        payload = run_release_check(
            workspace.resolve(), topic_video=video, licences=licences,
            shot_review_dir=shot_review_dir,
        )
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"status: {payload['status']}")
        for step in payload["steps"]:
            typer.echo(f"  [{step['status']}] {step['id']}: {step['detail']}")
        for step in payload["steps"]:
            for item in (step.get("data") or {}).get("hard_failures") or []:
                typer.echo(f"  ! {item.get('id')}: {item.get('detail')}")
    raise typer.Exit(
        0 if payload["status"] in {PASS, PASS_WITH_EXEMPTION}
        else (3 if payload["status"] == INCOMPLETE else 1)
    )


@app.command("build-manifest")
def build_manifest_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    video: Path | None = typer.Option(None, "--video", help="rendered film; defaults to the final video"),
    timing: Path | None = typer.Option(None, "--timing", help="episode timing.json"),
    meta: Path | None = typer.Option(None, "--meta", help="narration.resequenced.meta.json"),
    check: bool = typer.Option(False, "--check", help="verify the existing manifest only"),
    force: bool = typer.Option(False, "--force", help="fingerprint even if the film is older than an input"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Fingerprint a rendered film and the inputs it was built from.

    Writes build/<slug>/manifest.json with a content hash for every input and
    for the film, plus a build id. release-check compares these hashes before
    it falls back to mtimes.
    """
    from course_control.release.build_manifest import (
        BuildManifestError,
        check_freshness,
        manifest_path,
        write_manifest,
    )
    from course_control.release.check import _final_video

    workspace = workspace.resolve()
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if check:
        target = video or _final_video(paths)
        if target is None:
            typer.echo("no final video; pass --video", err=True)
            raise typer.Exit(1)
        freshness = check_freshness(paths, target)
        if as_json:
            typer.echo(json.dumps(freshness.as_dict(), ensure_ascii=False, indent=2))
        else:
            typer.echo(f"fresh: {freshness.fresh}")
            typer.echo(f"stale_by: {freshness.stale_by}")
            if freshness.build_id:
                typer.echo(f"build: {freshness.build_id}")
            if freshness.reason:
                typer.echo(f"reason: {freshness.reason}")
        raise typer.Exit(0 if freshness.fresh else 1)
    target = video or _final_video(paths)
    if target is None:
        typer.echo("no final video; pass --video", err=True)
        raise typer.Exit(1)
    try:
        payload = write_manifest(
            paths,
            workspace,
            target,
            timing=timing,
            meta=meta,
            render={"fps": paths.lesson.outputs.fps, "resolution": paths.lesson.outputs.resolution},
            allow_older=force,
        )
    except BuildManifestError as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"build: {payload['build_id']}")
        for entry in payload["inputs"]:
            typer.echo(f"  {entry['name']}: {entry['sha256'][:16]}… {entry['path']}")
        typer.echo(
            f"  output: {payload['output']['sha256'][:16]}… {payload['output']['path']}"
        )
        typer.echo(f"wrote: {manifest_path(paths)}")


@app.command("episode-build")
def episode_build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    video: Path | None = typer.Option(None, "--video", help="episode film with narration"),
    captioned: Path | None = typer.Option(None, "--captioned", help="subtitled master"),
    narration: Path | None = typer.Option(None, "--narration", help="narration track muxed into the film"),
    timing: Path | None = typer.Option(None, "--timing", help="episode timing.json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Record the episode render as final/build-report.json.

    Episode-based lessons do not run the deck build, so the quality gate had no
    report of its own and read the old deck report as stale.  This command
    records the film that exists: every artifact is hashed, every media file is
    probed, and the checks compare the film with the episode timeline.
    """
    from course_control.release.episode_build import EpisodeBuildError, record_episode_build

    workspace = workspace.resolve()
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    from course_control.authoring.pipeline import assert_storyboard_signed

    try:
        assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
        from course_control.release.check import content_exception_for

        exception = content_exception_for(paths.build_root, paths.slug)
        if exception is not None:
            raise RuntimeError(
                "open content exception: "
                + str(exception.get("reason") or exception.get("detail") or "see queue")
            )
    except Exception as exc:  # noqa: BLE001 - the gate is user-facing
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    film = (video or (paths.build_root / "final" / "course-video.mp4")).resolve()
    subtitled = (captioned or (paths.build_root / "final" / "course-video-captioned.mp4")).resolve()
    track = (narration or (paths.build_root / "narration" / "narration.resequenced.wav")).resolve()
    try:
        report, target = record_episode_build(
            paths,
            video=film,
            narration=track if track.is_file() else None,
            captioned=subtitled if subtitled.is_file() else None,
            timing=timing,
        )
    except EpisodeBuildError as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"verdict: {report.verdict}")
        for item in report.checks:
            typer.echo(f"  [{item.status.value}] {item.id}: {item.actual} (expected {item.expected})")
        for stage in report.stages:
            typer.echo(f"  [{stage.status.value}] {stage.name}")
        typer.echo(f"report: {target}")
    raise typer.Exit(1 if report.verdict == "fail" else 0)
