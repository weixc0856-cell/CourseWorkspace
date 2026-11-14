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
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    short_edge: int = typer.Option(480, "--short-edge"),
    force: bool = typer.Option(False, "--force"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run P0, P1 and P2 for one lesson and record the cost of each level."""
    from course_control.preview.profile import PreviewLevel, RenderMode
    from course_control.preview.runner import run_pilot

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
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
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run the delivery checks in order and print PASS / FAIL / INCOMPLETE."""
    from course_control.release.check import INCOMPLETE, run_release_check

    if bool(lesson) == bool(project):
        typer.echo("give exactly one of --lesson or --project", err=True)
        raise typer.Exit(2)
    if lesson:
        try:
            paths = _paths(workspace, lesson, lesson_dir)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        payload = run_release_check(workspace.resolve(), paths=paths)
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
            payload = run_release_check(workspace.resolve(), paths=paths)
            if as_json:
                typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                typer.echo(f"status: {payload['status']}")
                for step in payload["steps"]:
                    typer.echo(f"  [{step['status']}] {step['id']}: {step['detail']}")
            raise typer.Exit(
                0 if payload["status"] == "pass" else (3 if payload["status"] == INCOMPLETE else 1)
            )
        try:
            context = load_topic(workspace.resolve(), project)
        except Exception as exc:  # noqa: BLE001
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        video = context.delivery_dir / context.output_name
        licences = [item.model_dump(mode="json") for item in context.plan.licences]
        payload = run_release_check(
            workspace.resolve(), topic_video=video, licences=licences
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
    raise typer.Exit(0 if payload["status"] == "pass" else (3 if payload["status"] == INCOMPLETE else 1))
