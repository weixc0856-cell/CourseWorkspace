"""Resolve the content root used by CourseWorkspace.

This mirrors ``CourseControl/src/course_control/workspace_layout.py``.  ContentQA
is a standalone package and does not depend on CourseControl, so the small
resolver is duplicated rather than pulled in as a heavy dependency.

Resolution order: ``COURSEWORKSPACE_CONTENT_ROOT`` > ``config/local-paths.yaml``
``content_root`` > the workspace itself.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_REL = Path("config/local-paths.yaml")
ENV_VAR = "COURSEWORKSPACE_CONTENT_ROOT"
KEY = "content_root"


def content_root(workspace: Path) -> Path:
    workspace = Path(workspace).resolve()
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser().resolve()
    config = workspace / CONFIG_REL
    value = None
    if config.is_file():
        try:
            data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        if isinstance(data, dict):
            value = data.get(KEY)
    if value:
        candidate = Path(str(value)).expanduser()
        return candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    return workspace


def lessons_root(workspace: Path) -> Path:
    return content_root(workspace) / "lessons"


def lesson_path(workspace: Path, lesson_dir: Path | None, lesson: str) -> Path:
    base = lessons_root(workspace) if lesson_dir is None else Path(lesson_dir)
    if not base.is_absolute():
        base = Path(workspace) / base
    return (base / lesson).resolve()


def build_root_for(workspace: Path, slug: str) -> Path:
    return content_root(workspace) / "build" / slug
