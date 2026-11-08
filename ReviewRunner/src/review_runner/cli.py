"""CLI entry point: ``review-runner run``."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .runner import RunOptions, run_review
from .schema import Finding, FindingsEnvelope, Manifest, ReviewType

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("run")
def run_command(
    review_type: ReviewType = typer.Option(
        ReviewType.code, "--type", help="code (phase 1), docs, course"
    ),
    commit: str | None = typer.Option(None, "--commit", help="review one commit"),
    base: str | None = typer.Option(None, "--base", help="review merge-base(base, HEAD)..HEAD"),
    files: list[str] = typer.Option(
        [], "--files", help="explicit whitelist for docs review"
    ),
    context: list[str] = typer.Option(
        [], "--context", help="extra tracked files read from the same revision"
    ),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    output_root: Path | None = typer.Option(None, "--output-root"),
    allow_external_content: bool = typer.Option(
        False,
        "--allow-external-content",
        help="per-run grant to send course content to a remote provider",
    ),
    timeout_s: int = typer.Option(600, "--timeout"),
    no_isolation: bool = typer.Option(
        False,
        "--no-isolation",
        help="use the machine's ~/.codex config (MCP servers and catalog load again)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="prepare snapshot and budget only; do not call codex"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run one independent review and archive the evidence under build/reviews/."""
    options = RunOptions(
        review_type=review_type,
        commit=commit,
        base=base,
        files=tuple(files),
        context_files=tuple(context),
        workspace=workspace,
        output_root=output_root,
        allow_external_content=allow_external_content,
        timeout_s=timeout_s,
        isolated=not no_isolation,
        dry_run=dry_run,
    )
    outcome = run_review(options)
    if outcome.manifest is None:
        typer.echo(outcome.message, err=True)
        raise typer.Exit(outcome.exit_code)

    manifest = outcome.manifest
    if as_json:
        typer.echo(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)
        )
    else:
        typer.echo(f"review: {manifest.review_id}")
        typer.echo(f"execution: {manifest.execution_status.value}")
        typer.echo(f"review: {manifest.review_status.value}")
        typer.echo(
            f"findings: {manifest.findings_count if manifest.findings_count is not None else '-'}"
        )
        typer.echo(f"flags: {', '.join(manifest.flags) or '-'}")
        if manifest.budget:
            typer.echo(
                "tokens: estimated input "
                f"{manifest.budget.estimated_input_tokens}, actual input "
                f"{manifest.budget.actual_input_tokens if manifest.budget.actual_input_tokens is not None else '-'}"
            )
        typer.echo(f"production_effect: {manifest.production_effect}")
        if manifest.blocked_reason:
            typer.echo(f"reason: {manifest.blocked_reason}", err=True)
        typer.echo(f"message: {outcome.message}")
    if outcome.exit_code != 0:
        raise typer.Exit(outcome.exit_code)


@app.command("schema")
def schema_command(
    output: Path = typer.Option(
        Path(__file__).resolve().parents[2] / "schemas", "--output"
    ),
) -> None:
    """Export JSON Schemas for the review contracts."""
    output.mkdir(parents=True, exist_ok=True)
    models = {
        "review-manifest": Manifest,
        "review-finding": Finding,
        "review-findings": FindingsEnvelope,
    }
    for name, model in models.items():
        target = output / f"{name}.schema.json"
        target.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        typer.echo(str(target))


if __name__ == "__main__":  # pragma: no cover
    app()
