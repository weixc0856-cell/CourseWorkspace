"""Resolve the CourseWorkspace content root.

Mirrors ``CourseControl/src/course_control/workspace_layout.py``; ReviewRunner is
a standalone package, so the small resolver is copied rather than imported.
Order: ``COURSEWORKSPACE_CONTENT_ROOT`` > ``config/local-paths.yaml`` > workspace.
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
