from __future__ import annotations

from pathlib import Path

import typer

from . import app
from course_control.cli._common import _paths
from course_control.content.paths import ContractError
from course_control.production.preflight import run_preflight


@app.command("preflight")
def preflight_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    strict: bool = typer.Option(False, "--strict", help="treat warnings as errors"),
) -> None:
    """Check episode.spec.yaml and quality.rubric.yaml before any render."""
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = run_preflight(paths.lesson_dir, strict=strict, paths=paths)
    typer.echo(f"lesson: {report.lesson}")
    if report.spec is not None:
        typer.echo(f"episode: {report.spec.episode}")
        typer.echo(f"beats: {len(report.spec.beats)} ({report.spec.total_seconds}s)")
        typer.echo(f"claims: {len(report.spec.claims)}")
    for warning in report.warnings:
        typer.echo(f"  [warn] {warning}")
    for error in report.errors:
        typer.echo(f"  [error] {error}")
    typer.echo("status: " + ("PASS" if report.ok else "FAIL"))
    raise typer.Exit(0 if report.ok else 1)


@app.command("checks")
def checks_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    stage: str = typer.Option("spec", "--stage"),
    book_index: Path | None = typer.Option(None, "--book-index", help="book index.json used by claim_source_coverage"),
    strict: bool = typer.Option(False, "--strict", help="review items also fail the run"),
) -> None:
    """Run typed auto/review checks and write an exception queue."""
    import json

    from course_control.production.checks import run_checks
    from course_control.production.episode_spec import load_episode_spec
    from course_control.production.quality_rubric import load_quality_rubric

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        spec = load_episode_spec(paths.lesson_dir / "authoring" / "episode.spec.yaml")
        rubric = load_quality_rubric(paths.lesson_dir / "authoring" / "quality.rubric.yaml")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"checks failed to load: {exc}", err=True)
        raise typer.Exit(1)
    report = run_checks(spec, rubric, paths.lesson_dir, paths.build_root, book_index=book_index)
    typer.echo(f"book index: {book_index if book_index else 'not provided'}")
    for result in report.results:
        typer.echo(f"  [{result.status}] {result.id} ({result.kind}): {result.actual!r}")
    payload = report.as_dict(stage)
    target = paths.build_root / "quality" / "exceptions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"exceptions: {target}")
    review_open = bool(report.review_open)
    failed = bool(report.auto_failed) or (strict and review_open)
    # Review items are not auto checks: an open review is INCOMPLETE, never
    # PASS.  Only --strict turns it into a failure.
    incomplete = (not failed) and review_open
    typer.echo("status: " + ("FAIL" if failed else ("INCOMPLETE" if incomplete else "PASS")))
    raise typer.Exit(1 if failed else (2 if incomplete else 0))

@app.command("book-index")
def book_index_command(
    index: Path = typer.Option(..., "--index", help="book/index.json"),
    cards_dir: Path = typer.Option(..., "--cards-dir", help="episodes directory with */card.yaml"),
    map_path: Path | None = typer.Option(None, "--map", help="COURSE_MAP.md with the episode table"),
) -> None:
    """Check episode cards against the book index and the course map."""
    from course_control.production.book_index import (
        BookIndexError,
        check_cards,
        load_book_index,
        load_card_dir,
        load_course_map,
    )

    try:
        data = load_book_index(index)
        cards = load_card_dir(cards_dir)
        map_episodes = load_course_map(map_path) if map_path is not None else None
    except BookIndexError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    problems = check_cards(data, cards, map_episodes)
    typer.echo(f"book index: {index}")
    typer.echo(f"cards: {len(cards)}")
    if map_episodes is not None:
        typer.echo(f"map: {map_path} ({len(map_episodes)} episodes)")
    for problem in problems:
        typer.echo(f"  [error] {problem}")
    typer.echo("status: " + ("PASS" if not problems else "FAIL"))
    raise typer.Exit(0 if not problems else 1)

@app.command("contract-validate")
def contract_validate_command(
    kind: str = typer.Option(..., "--kind", help="product | ledger | timeline"),
    path: Path = typer.Option(..., "--path", help="YAML or JSON contract file"),
) -> None:
    """Validate a product profile, asset ledger or production timeline."""
    from course_control.production.contracts import ContractModelError, load_contract

    try:
        model = load_contract(kind, path)
    except ContractModelError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"{kind}: ok  ({model.__class__.__name__})")
    raise typer.Exit(0)


@app.command("contract-schemas")
def contract_schemas_command(
    output: Path = typer.Option(Path("shared/schemas"), "--output"),
) -> None:
    """Export product/ledger/timeline JSON Schema from their models."""
    from course_control.production.contracts import export_schemas

    for target in export_schemas(output):
        typer.echo(f"wrote {target}")

@app.command("retime")
def retime_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Recompute beat timing from the measured narration track."""
    from course_control.production.retime import RetimeError, write_retime

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    mapping = paths.lesson_dir / "authoring" / "beat-segments.yaml"
    meta = paths.build_root / "narration" / "narration.meta.json"
    try:
        timings = write_retime(paths.lesson_dir, paths.build_root, mapping, meta)
    except RetimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    for item in timings:
        typer.echo(f"  {item.id} {item.type}: {item.seconds}s ({item.start_s}-{item.end_s})")
    typer.echo(f"total: {round(sum(item.seconds for item in timings), 3)}s")
    typer.echo(f"written: {paths.lesson_dir / 'authoring' / 'beat-timing.md'}")

@app.command("beat-plan")
def beat_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate the beat plan: instance durations must add up to each beat."""
    from course_control.production.beat_plan import BeatPlanError, load_plan

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        beats = load_plan(paths.lesson_dir / "authoring" / "beat-segments.yaml")
    except BeatPlanError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    for beat in beats:
        typer.echo(f"  {beat.id}: {beat.seconds}s = " + " + ".join(f"{i.component} {i.duration}s" for i in beat.instances))
    typer.echo(f"total: {round(sum(b.seconds for b in beats), 3)}s")

