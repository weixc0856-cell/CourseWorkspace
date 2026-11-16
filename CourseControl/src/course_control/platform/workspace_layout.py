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
MODE_ENV = "COURSEWORKSPACE_MODE"
DEV_ROOT_ENV = "COURSEWORKSPACE_DEV_ROOT"
DEV_WORKSPACE_ENV = "COURSEWORKSPACE_DEV_WORKSPACE"
KEY = "content_root"


def dev_mode() -> bool:
    """Development runs must never resolve the production content root."""
    return os.environ.get(MODE_ENV, "").strip().lower() == "dev"


def content_root_source(workspace: Path) -> str:
    """Where the root came from: dev, dev-workspace, env, config or workspace."""
    return _cached(workspace)[1]


def _configured_root(workspace: Path) -> Path | None:
    config = workspace / CONFIG_REL
    if not config.is_file():
        return None
    try:
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    value = data.get(KEY) if isinstance(data, dict) else None
    if not value:
        return None
    candidate = Path(str(value)).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (workspace / candidate).resolve()


def _production_hint(workspace: Path) -> Path | None:
    dev_workspace = os.environ.get(DEV_WORKSPACE_ENV)
    if not dev_workspace:
        return None
    return _configured_root(Path(dev_workspace).resolve())


def _inside_hint(path: Path, hint: Path | None) -> bool:
    if hint is None:
        return False
    try:
        path.resolve().relative_to(hint.resolve())
    except ValueError:
        return path.resolve() == hint.resolve()
    return True


def _dev_temp_root(workspace: Path) -> tuple[Path, str]:
    hint = _production_hint(workspace)
    env = os.environ.get(ENV_VAR)
    if env:
        candidate = Path(env).expanduser().resolve()
        if _inside_hint(candidate, hint):
            raise RuntimeError(
                "dev mode refuses a content root inside the production root"
            )
        return candidate, "dev-env"
    configured = _configured_root(workspace)
    if configured is not None:
        if _inside_hint(configured, hint):
            raise RuntimeError(
                "dev mode refuses a content root inside the production root"
            )
        return configured, "dev-config"
    return workspace, "dev-workspace"


def _env_key() -> tuple[str | None, ...]:
    return (
        os.environ.get(MODE_ENV),
        os.environ.get(DEV_ROOT_ENV),
        os.environ.get(DEV_WORKSPACE_ENV),
        os.environ.get(ENV_VAR),
    )


def _resolve(workspace: Path) -> tuple[Path, str]:
    workspace = workspace.resolve()
    if dev_mode():
        dev_root = os.environ.get(DEV_ROOT_ENV)
        dev_workspace = os.environ.get(DEV_WORKSPACE_ENV)
        if not dev_root or not dev_workspace:
            raise RuntimeError(
                "dev mode requires COURSEWORKSPACE_DEV_ROOT and "
                "COURSEWORKSPACE_DEV_WORKSPACE; it never falls back to the "
                "production config"
            )
        if workspace == Path(dev_workspace).resolve():
            return Path(dev_root).expanduser().resolve(), "dev"
        # A temporary workspace (a test) may name its own temp root through the
        # env or a local config; a root inside the production root is refused.
        return _dev_temp_root(workspace)
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env).expanduser().resolve(), "env"
    configured = _configured_root(workspace)
    if configured is not None:
        return configured, "config"
    return workspace, "workspace"


# resolved root keyed by workspace -> (env tuple, config mtime, root, source)
_cache: dict[Path, tuple[tuple[str | None, ...], float | None, Path, str]] = {}


def _cached(workspace: Path) -> tuple[Path, str]:
    workspace = Path(workspace).resolve()
    config = workspace / CONFIG_REL
    try:
        mtime = config.stat().st_mtime
    except OSError:
        mtime = None
    key = _env_key()
    cached = _cache.get(workspace)
    if cached is not None and cached[0] == key and cached[1] == mtime:
        return cached[2], cached[3]
    root, source = _resolve(workspace)
    _cache[workspace] = (key, mtime, root, source)
    return root, source


def content_root(workspace: Path) -> Path:
    """The directory that holds lessons, build, deliver and runtime."""
    return _cached(workspace)[0]


def production_content_root(workspace: Path) -> Path:
    """An explicit production root for release, package and release approval.

    Refuses dev mode and refuses the silent "the workspace is the content
    root" fallback; production commands must name the root with
    ``COURSEWORKSPACE_CONTENT_ROOT`` or ``config/local-paths.yaml``.
    """
    if dev_mode():
        raise RuntimeError(
            "production commands are refused in dev mode; "
            "run them against the production content root explicitly"
        )
    root, source = _cached(workspace)
    if source == "workspace":
        raise RuntimeError(
            "production command needs an explicit content root "
            "(COURSEWORKSPACE_CONTENT_ROOT or config/local-paths.yaml), "
            "not the workspace"
        )
    return root


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


def is_course_lesson(workspace: Path, lesson_dir: Path) -> bool:
    """True when the lesson lives under <content_root>/lessons.

    Fixtures and samples live in the repository; they are not course lessons
    and must not be stopped by the storyboard sign-off gate.
    """
    # Lexical containment: resolving here would follow a junction and let a
    # course lesson masquerade as a non-course directory, skipping the gate.
    lessons = Path(os.path.abspath(content_root(workspace) / "lessons"))
    candidate = Path(os.path.abspath(lesson_dir))
    try:
        candidate.relative_to(lessons)
    except ValueError:
        return False
    return True


def build_root_for(workspace: Path, slug: str) -> Path:
    return content_root(workspace) / "build" / slug


def build_root(workspace: Path) -> Path:
    return content_root(workspace) / "build"


def delivery_root_for(workspace: Path, slug: str) -> Path:
    # Deliberately lexical: resolving here would follow a junction at
    # deliver/<slug> and let the package write outside the content root.
    return content_root(workspace) / "deliver" / slug


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
