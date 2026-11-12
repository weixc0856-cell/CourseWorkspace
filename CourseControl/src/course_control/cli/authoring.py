from __future__ import annotations

import json

import typer

from pathlib import Path

from course_control.content.paths import ContractError, LessonPaths

from . import app
from course_control.cli._common import _authoring_client, _load_authoring, _run_authoring, _lesson_path


@app.command("ingest")
def ingest_command(
    lesson: str = typer.Option(..., "--lesson"),
    source: str = typer.Option(..., "--source"),
    kind: str = typer.Option("auto", "--kind"),
    source_id: str | None = typer.Option(None, "--id"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Fetch/copy one source into lessons/<slug>/authoring/sources/."""
    from course_control.authoring.ingest import IngestError, ingest

    try:
        entry = ingest(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            source,
            kind=kind,
            source_id=source_id,
        )
    except IngestError as exc:
        typer.echo(f"ingest failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"source: {entry.id} ({entry.kind})")
    typer.echo(f"local: {entry.local_path}")
    typer.echo(f"sha256: {entry.sha256}")


@app.command("digest")
def digest_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
) -> None:
    """Build a deterministic source digest with stable citation refs."""
    from course_control.authoring.digest import build_digest

    try:
        digest = build_digest(_lesson_path(workspace, lesson_dir, lesson))
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"digest failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"sources: {len(digest.sources)}")
    typer.echo(f"sections: {len(digest.sections)}")
    typer.echo(f"digest: {digest.lesson}")


@app.command("brief")
def brief_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate a course brief candidate from the approved source digest."""
    from course_control.authoring.digest import load_digest
    from course_control.authoring.pipeline import generate_brief

    def action() -> None:
        root = _lesson_path(workspace, lesson_dir, lesson)
        digest = load_digest(root / "authoring" / "source-digest.json")
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            brief = generate_brief(client, workspace.resolve(), root, digest)
        typer.echo(f"brief: {brief.lesson} ({len(brief.objectives)} objectives)")

    _run_authoring(action)


@app.command("outline")
def outline_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate an outline candidate from the approved brief."""
    from course_control.authoring.digest import load_digest
    from course_control.authoring.models import Brief
    from course_control.authoring.pipeline import generate_outline

    def action() -> None:
        root = _lesson_path(workspace, lesson_dir, lesson)
        digest = load_digest(root / "authoring" / "source-digest.json")
        brief = _load_authoring(root, "brief.json", Brief)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            outline = generate_outline(client, workspace.resolve(), root, digest, brief)
        typer.echo(f"outline: {len(outline.pages)} pages")

    _run_authoring(action)


@app.command("script")
def script_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate the English emotional narration script candidate."""
    from course_control.authoring.digest import load_digest
    from course_control.authoring.models import Outline
    from course_control.authoring.pipeline import generate_script

    def action() -> None:
        root = _lesson_path(workspace, lesson_dir, lesson)
        digest = load_digest(root / "authoring" / "source-digest.json")
        outline = _load_authoring(root, "outline.json", Outline)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            script = generate_script(client, workspace.resolve(), root, digest, outline)
        typer.echo(f"script: {len(script.pages)} pages")

    _run_authoring(action)


@app.command("content-draft")
def content_draft_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate candidate slides, notes and storyboard from approved outline/script."""
    from course_control.authoring.digest import load_digest
    from course_control.authoring.models import NarrationScript, Outline
    from course_control.authoring.pipeline import generate_content

    def action() -> None:
        root = _lesson_path(workspace, lesson_dir, lesson)
        digest = load_digest(root / "authoring" / "source-digest.json")
        outline = _load_authoring(root, "outline.json", Outline)
        script = _load_authoring(root, "narration.script.json", NarrationScript)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            paths = generate_content(
                client, workspace.resolve(), root, digest, outline, script
            )
        for name, path in paths.items():
            typer.echo(f"{name}: {path}")

    _run_authoring(action)


@app.command("author-accept")
def author_accept_command(
    lesson: str = typer.Option(..., "--lesson"),
    kind: str = typer.Option(..., "--kind"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Human gate: promote a candidate artifact and record its sha256."""
    from course_control.authoring.pipeline import accept_artifact, accept_content

    root = _lesson_path(workspace, lesson_dir, lesson)
    try:
        if kind == "content":
            written = accept_content(workspace.resolve(), root)
        else:
            written = accept_artifact(workspace.resolve(), root, kind)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"accept failed: {exc}", err=True)
        raise typer.Exit(1)
    for path in written:
        typer.echo(f"accepted: {path}")


@app.command("narration-build")
def narration_build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    mode: str | None = typer.Option(None, "--mode"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    force: bool = typer.Option(False, "--force"),
    only_segment: str | None = typer.Option(None, "--segment-id"),
    sample_pages: int = typer.Option(0, "--sample-pages", min=0),
    dry_run: bool = typer.Option(False, "--dry-run"),
    wait_timeout_s: int = typer.Option(1800, "--wait-timeout-s"),
) -> None:
    """Synthesize the whole course narration and write measured page spans."""
    from course_control.authoring.models import NarrationScript
    from course_control.voice.narration_course import (
        NarrationCourseBlocked,
        NarrationCourseError,
        dry_run as estimate,
        synthesize_course,
    )
    from course_control.authoring.pipeline import assert_approved

    workspace = workspace.resolve()
    root = _lesson_path(workspace, lesson_dir, lesson)
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    script_relative = (
        paths.lesson.authoring.script
        if paths.lesson.authoring and paths.lesson.authoring.script
        else "authoring/narration.script.json"
    )
    script_path = root / script_relative
    if not script_path.is_file():
        typer.echo(f"script not found: {script_path}", err=True)
        raise typer.Exit(1)
    script = NarrationScript.model_validate(
        json.loads(script_path.read_text(encoding="utf-8"))
    )
    if dry_run:
        info = estimate(script)
        for key, value in info.items():
            typer.echo(f"{key}: {value}")
        raise typer.Exit(0)
    try:
        assert_approved(root, script_relative)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"script is not approved: {exc}", err=True)
        raise typer.Exit(1)
    if mode:
        paths.lesson.narration.mode = mode
    try:
        meta = synthesize_course(
            workspace,
            paths,
            script,
            start_service=start_service,
            wait_timeout_s=wait_timeout_s,
            force=force,
            only_segment=only_segment,
            sample=sample_pages > 0,
            page_limit=sample_pages or None,
        )
    except NarrationCourseBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (NarrationCourseError, ContractError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"segments: {meta['totals']['segments']} (cache hits: {meta['totals']['cache_hits']})")
    typer.echo(f"audio: {meta['assembly']['duration_s']} s")
    if sample_pages:
        typer.echo(f"sample: {paths.build_root / 'narration' / 'sample' / 'sample.wav'}")
    else:
        typer.echo(f"meta: {paths.build_root / 'narration' / 'narration.meta.json'}")


@app.command("shot-sheet")
def shot_sheet_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compile storyboard.yaml as a shot sheet: resolved refs, fingerprints, review."""
    from course_control.authoring import shot_sheet

    workspace = workspace.resolve()
    try:
        paths = LessonPaths.load(workspace, _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    plan = shot_sheet.compile_sheet(paths)
    outputs = shot_sheet.write(paths, plan)
    summary = plan["summary"]

    if as_json:
        typer.echo(
            json.dumps(
                {
                    **summary,
                    "status": "blocked" if plan["issues"] else "ok",
                    "issues": plan["issues"],
                    "outputs": {name: str(path) for name, path in outputs.items()},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        typer.echo(
            f"sheet: {plan['source']['path']} (schema v{plan['source']['schema_version']})"
        )
        typer.echo(
            f"shots: {summary['shots']} ({summary['designed']} with sheet fields)  "
            f"continuity: {summary['continuity_objects']}  "
            f"assets: {summary['with_assets']}  evidence: {summary['with_evidence']}"
        )
        if summary["unused_continuity"]:
            typer.echo("unused continuity: " + ", ".join(summary["unused_continuity"]))
        for issue in plan["issues"]:
            typer.echo(f"  [{issue['rule']}] {issue['message']}", err=True)
        for name, path in outputs.items():
            typer.echo(f"{name}: {path}")
    raise typer.Exit(1 if plan["issues"] else 0)
