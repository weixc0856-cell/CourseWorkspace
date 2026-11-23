"""Centralized path resolution for CourseWorkspace and Content Root.

Ensures scripts, CLI, and agents transparently resolve:
1. Code Workspace: Relative to repository root (./)
2. Content Root: Resolved via environment variable, local config, or relative Directory Junction (./content_data)

Resolution priority for Content Root:
1. Environment variable: COURSEWORKSPACE_CONTENT_ROOT
2. config/local-paths.yaml: content_root
3. Directory Junction: <workspace>/content_data
4. Default relative fallback: <workspace>/content_data or <workspace>
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
try:
    import yaml
except ImportError:
    yaml = None


def get_workspace_root() -> Path:
    """Return the absolute path of CourseWorkspace."""
    # Anchored relative to this file: scripts/resolve_paths.py -> workspace root
    return Path(__file__).resolve().parent.parent


def get_content_root(workspace: Optional[Path] = None) -> Path:
    """Resolve the authoritative content root directory dynamically."""
    if workspace is None:
        workspace = get_workspace_root()

    # 1. Environment variable
    env_root = os.environ.get("COURSEWORKSPACE_CONTENT_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if p.exists():
            return p

    # 2. config/local-paths.yaml
    config_file = workspace / "config" / "local-paths.yaml"
    if config_file.is_file():
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            val = cfg.get("content_root")
            if val:
                p = Path(val).expanduser()
                if not p.is_absolute():
                    p = (workspace / p).resolve()
                if p.exists():
                    return p
        except Exception:
            pass

    # 3. Directory Junction: content_data
    junction = workspace / "content_data"
    if junction.is_dir() and (junction / "projects").exists():
        return junction.resolve()

    # 4. Relative fallback to junction or workspace
    if junction.exists():
        return junction.resolve()

    return workspace.resolve()


def get_course_map_path(course_id: str = "automotive-aerodynamics", workspace: Optional[Path] = None) -> Path:
    """Get the path to COURSE_MAP.md for a given course."""
    root = get_content_root(workspace)
    return root / "runtime" / "course-content" / course_id / "COURSE_MAP.md"


def get_episodes_dir(course_id: str = "automotive-aerodynamics", workspace: Optional[Path] = None) -> Path:
    """Get the episodes card directory for a given course."""
    root = get_content_root(workspace)
    return root / "runtime" / "course-content" / course_id / "episodes"


def get_project_yaml_path(course_id: str = "automotive-aerodynamics", workspace: Optional[Path] = None) -> Path:
    """Get the project.yaml path for a given course."""
    root = get_content_root(workspace)
    return root / "projects" / course_id / "project.yaml"


def get_build_dir(lesson_slug: str, workspace: Optional[Path] = None) -> Path:
    """Get the build directory for a specific lesson/episode under Content Root."""
    root = get_content_root(workspace)
    d = root / "build" / lesson_slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_deliver_dir(lesson_slug: str, workspace: Optional[Path] = None) -> Path:
    """Get the deliver directory for a specific lesson/episode under Content Root."""
    root = get_content_root(workspace)
    d = root / "deliver" / lesson_slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_runtime_state_dir(workspace: Optional[Path] = None) -> Path:
    """Get the runtime state directory under Content Root."""
    root = get_content_root(workspace)
    d = root / "runtime" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_pipeline_db_path(workspace: Optional[Path] = None) -> Path:
    """Get the authoritative pipeline state database path under Content Root."""
    state_dir = get_runtime_state_dir(workspace)
    return state_dir / "aerodynamics_pipeline.db"


def get_scientific_figures_dir(course_id: str = "automotive-aerodynamics", workspace: Optional[Path] = None) -> Path:
    """Get the scientific figures project directory for a course under Content Root."""
    root = get_content_root(workspace)
    d = root / "projects" / course_id / "ScientificFigures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_templates_dir(workspace: Optional[Path] = None) -> Path:
    """Get the course templates directory under Content Root."""
    root = get_content_root(workspace)
    d = root / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_and_ensure_junction(workspace: Optional[Path] = None) -> tuple[bool, str]:
    """Check if content_data junction exists, and create it on Windows if needed."""
    if workspace is None:
        workspace = get_workspace_root()

    junction = workspace / "content_data"
    content_root = get_content_root(workspace)

    if junction.exists():
        return True, f"Junction exists: {junction.name} -> {content_root}"

    if sys.platform == "win32":
        try:
            cmd = f'cmd /c mklink /J "{junction}" "{content_root}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0 and junction.exists():
                return True, f"Created Directory Junction: {junction.name} -> {content_root}"
            return False, f"Failed to create junction: {res.stderr or res.stdout}"
        except Exception as e:
            return False, f"Exception creating junction: {e}"

    return False, "Non-Windows OS: junction not created"


if __name__ == "__main__":
    ws = get_workspace_root()
    cr = get_content_root(ws)
    print(f"Workspace Root: {ws}")
    print(f"Content Root  : {cr}")
    ok, msg = check_and_ensure_junction(ws)
    print(f"Junction Status: {msg}")
    print(f"Course Map Path: {get_course_map_path()}")
    print(f"Episodes Dir   : {get_episodes_dir()}")
