"""Where course content lives, kept separate from where the pipeline code lives.

The workspace holds the pipeline (CourseControl, engines, shared, docs).  Course
content -- lessons, build output, delivery packages, runtime state -- may live
in a separate directory so that ``ls`` on the workspace shows code only.

Resolution order (later wins):

1. the workspace itself (default: everything stays where it always was)
2. ``config/local-paths.yaml`` -> ``content_root``
3. ``COURSEWORKSPACE_CONTENT_ROOT`` environment variable

Relative values in the config are resolved against the workspace; absolute
values are used as given.  Nothing here changes file names or directory
structure under the root, so ``build/<slug>/`` stays ``build/<slug>/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_REL = Path("config/local-paths.yaml")
ENV_VAR = "COURSEWORKSPACE_CONTENT_ROOT"
KEY = "content_root"

# resolved root keyed by workspace -> (env value, config mtime, root)
_cache: dict[Path, tuple[str | None, float | None, Path]] = {}


def content_root(workspace: Path) -> Path:
    """Return the directory that holds lessons, build, deliver and runtime."""
    workspace = Path(workspace).resolve()
    config = workspace / CONFIG_REL
    try:
        mtime = config.stat().st_mtime
    except OSError:
        mtime = None
    env = os.environ.get(ENV_VAR)
    cached = _cache.get(workspace)
    if cached is not None and cached[0] == env and cached[1] == mtime:
        return cached[2]
    root = _resolve(workspace, config, env)
    _cache[workspace] = (env, mtime, root)
    return root


def _resolve(workspace: Path, config: Path, env: str | None) -> Path:
    if env:
        return Path(env).expanduser().resolve()
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
        if candidate.is_absolute():
            return candidate.resolve()
        return (workspace / candidate).resolve()
    return workspace


def lessons_root(workspace: Path) -> Path:
    return content_root(workspace) / "lessons"


def build_root_for(workspace: Path, slug: str) -> Path:
    return content_root(workspace) / "build" / slug


def build_root(workspace: Path) -> Path:
    return content_root(workspace) / "build"


def delivery_root_for(workspace: Path, slug: str) -> Path:
    return (content_root(workspace) / "deliver" / slug).resolve()


def runtime_root(workspace: Path) -> Path:
    return content_root(workspace) / "runtime"


def reset_cache() -> None:
    """Drop memoised roots; used by tests that rewrite the config."""
    _cache.clear()
