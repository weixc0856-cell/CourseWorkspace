"""Command-line entry point for :mod:`course_control`."""
from __future__ import annotations

import sys

import typer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(no_args_is_help=True, add_completion=False)

# Command modules register themselves on import; order here is the order Typer
# lists them in ``--help``.
from . import (  # noqa: E402,F401
    animatic,
    authoring,
    design,
    director,
    legacy,
    lesson,
    locks,
    preview,
    producer,
    project,
    quality,
    render,
    scene,
    session,
    sound,
)

# 90 commands in one flat list made the entry point unreadable.  Grouping is
# presentation only: every command, flag and behaviour stays exactly as it was.
# The audit behind this split is docs/生产复杂度审计.md.
_HELP_PANELS: dict[str, str] = {}
for _panel, _names in {
    "Build & verify": (
        "build validate verify schemas schemas-v1 contract-v1-validate content-root "
        "separation layout-templates layout-validate"
    ),
    "Authoring": (
        "ingest digest brief outline script content-draft author-accept narration-build shot-sheet"
    ),
    "Director & design": (
        "director-plan director-validate direction-validate beats-validate animation-score "
        "narrative-validate teaching-qa plan-audit shot-taxonomy grammar-list "
        "production-validate quality-gate reference-compare visual-design sound-design"
    ),
    "Produce & deliver": (
        "producer-order producer-run producer-status producer-affected producer-rebuild "
        "package package-verify release-approve review-status review-decide vendor-check "
        "vendor-sync stats config-resolve project-validate project-show artifact-index "
        "run-start run-status quality-diagnose quality-repair-plan quality-regression "
        "quality-certificate release-check lock lock-status"
    ),
    "Render & audio": (
        "tts-status narrate narration-assets subtitles-build subtitles-retime subtitles-rewrap "
        "subtitles-accept burn-subs subtitles-qc audio-plan audio-mix media-qc "
        "quality-report asr-align"
    ),
    "Scenes & 3D": (
        "scene-validate scene-schema scene-run blender-task-validate simulation-validate "
        "simulation-run formula-validate formula-render formula-video-qc formula-audit "
        "brand-plan brand-render"
    ),
    "Preview": "animatic preview-pilot session-validate session-run session-evidence-v1",
    "Legacy": "e6-adapt e65-adapt timeline-v1",
}.items():
    for _name in _names.split():
        _HELP_PANELS[_name] = _panel

for _command in app.registered_commands:
    _panel = _HELP_PANELS.get(_command.name or "")
    if _panel is None and _command.callback is not None:
        if _command.callback.__module__.endswith(".lesson"):
            _panel = "Build & verify"
    if _panel:
        _command.rich_help_panel = _panel


if __name__ == "__main__":
    app()
