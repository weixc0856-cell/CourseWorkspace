"""One vendored three.js, copied into shots at build time.

The capture server serves only the shot directory, so a shot cannot import
``../../vendor/three.module.js``.  The previous answer was five checked-in
copies (about 265k lines).  The canonical file now lives once under
``CodeVideoStudio/vendor/three/`` and every capture copies it into the shot
directory first.  The copies are build artifacts, not sources.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from course_control.platform.workspace_layout import engine_root

VENDOR_RELATIVE = Path("CodeVideoStudio") / "vendor" / "three" / "three.module.js"
TARGET_NAME = "three.module.js"


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def vendor_path(workspace: Path) -> Path:
    return (workspace / VENDOR_RELATIVE).resolve()


def uses_three(project: Path) -> bool:
    """A shot uses three.js when its page or entry script imports the module."""
    for name in ("index.html", "main.js"):
        path = project / name
        if path.is_file() and "three.module.js" in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    return False


def sync_one(workspace: Path, project: Path) -> str:
    """Copy the canonical build into one shot; return ``copied`` or ``current``."""
    source = vendor_path(workspace)
    if not source.is_file():
        raise FileNotFoundError(f"canonical three.js is missing: {source}")
    target = project / TARGET_NAME
    if target.is_file() and _sha(target) == _sha(source):
        return "current"
    target.write_bytes(source.read_bytes())
    return "copied"


def sync(workspace: Path, projects: list[Path]) -> dict:
    result = {"copied": [], "current": [], "errors": []}
    for project in projects:
        try:
            status = sync_one(workspace, project)
        except (OSError, FileNotFoundError) as exc:
            result["errors"].append(f"{project.name}: {exc}")
            continue
        result[status].append(project.name)
    return result


def audit(workspace: Path) -> list[str]:
    """Report shots whose local copy is missing or differs from the canonical file."""
    source = vendor_path(workspace)
    if not source.is_file():
        return [f"canonical three.js is missing: {source}"]
    digest = _sha(source)
    problems: list[str] = []
    shots = engine_root(workspace, "code_video") / "shots"
    if not shots.is_dir():
        return problems
    for project in sorted(path for path in shots.iterdir() if path.is_dir()):
        if not uses_three(project):
            continue
        target = project / TARGET_NAME
        if not target.is_file():
            problems.append(f"{project.name}: copy missing (run vendor-sync)")
        elif _sha(target) != digest:
            problems.append(f"{project.name}: copy differs from vendor/three")
    return problems


__all__ = [
    "TARGET_NAME",
    "VENDOR_RELATIVE",
    "audit",
    "sync",
    "sync_one",
    "uses_three",
    "vendor_path",
]
