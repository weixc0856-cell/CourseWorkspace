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


# Engine project directories inside the workspace (skills, scripts, venvs) and
# their scene directories inside the content root (``<content_root>/engines/``).
ENGINE_DIRS = {
    "motion_canvas": "MotionStudio",
    "manim": "ManimSandbox",
    "blender": "BlenderStudio",
    "code_video": "CodeVideoStudio",
}
ENGINE_CONTENT = {
    "motion_canvas": "motion_canvas",
    "manim": "manim",
    "blender": "blender",
    "code_video": "code_video",
}


def engine_roots(workspace: Path, engine: str, content_base: Path | None = None) -> list[Path]:
    """Where an engine's scenes may live, most specific first.

    Course scenes move to the content root when one is configured; the
    workspace engine directory stays as the fallback so fixtures, samples and a
    clean clone keep working.
    """
    try:
        home = (Path(workspace).resolve() / ENGINE_DIRS[engine]).resolve()
    except KeyError as exc:
        raise ValueError(f"unknown engine: {engine}") from exc
    base = Path(content_base).resolve() if content_base is not None else content_root(workspace)
    roots: list[Path] = []
    if base != Path(workspace).resolve():
        candidate = (base / "engines" / ENGINE_CONTENT[engine]).resolve()
        if candidate.is_dir():
            roots.append(candidate)
    roots.append(home)
    return roots


def engine_root(workspace: Path, engine: str, content_base: Path | None = None) -> Path:
    """The preferred scene root for one engine."""
    return engine_roots(workspace, engine, content_base)[0]


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


def projects_root(workspace: Path) -> Path:
    """Series and project material: ``<content_root>/projects/<id>/``."""
    return content_root(workspace) / "projects"


def audio_root(workspace: Path) -> Path:
    """Shared voice assets: voice bibles and lexicons."""
    return content_root(workspace) / "audio"


def reset_cache() -> None:
    """Drop memoised roots; used by tests that rewrite the config."""
    _cache.clear()
