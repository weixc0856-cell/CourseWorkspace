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
    director,
    legacy,
    lesson,
    locks,
    producer,
    project,
    quality,
    render,
    scene,
    session,
)

if __name__ == "__main__":
    app()
