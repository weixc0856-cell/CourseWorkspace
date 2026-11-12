"""Course files belong in the content root, never in the program workspace.

The workspace holds the pipeline: code, schemas, fixtures, scripts and docs.
Course content -- lessons, engine scenes, render tasks, narration, media --
lives under the content root and is not committed here.

The rule is checked, not assumed: any directory named after a lesson inside the
workspace is reported.  Two exceptions exist and each carries its reason:

* fixtures the test suite owns (a lesson-shaped name, but test data);
* directory junctions, where only the path lives in the repository and the
  bytes do not.  Junctions are skipped, because the files are not stored here.
"""

from __future__ import annotations

import os
from pathlib import Path

from course_control.platform.workspace_layout import content_root, lessons_root

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

# Lesson-named paths that stay in the repository on purpose.
# Empty since 2026-11-12: the last three lesson-shaped directories became content-root
# paths behind junctions.  Add an entry only together with its reason.
ALLOWED: dict[str, str] = {}


# Prose and contracts belong in docs/; anything else there is project material or a
# stray artefact.  Reported as a warning: a deliberate diagram is fine, a video is not.
DOC_PROSE_SUFFIXES = {".md", ".yaml", ".yml"}
DOC_PROGRAM_PATHS = ("docs/contracts/",)


def docs_data_files(workspace: Path) -> list[str]:
    docs = Path(workspace).resolve() / "docs"
    if not docs.is_dir():
        return []
    found: list[str] = []
    for path in sorted(docs.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(Path(workspace).resolve()).as_posix()
        if path.suffix.lower() in DOC_PROSE_SUFFIXES:
            continue
        if relative.startswith(DOC_PROGRAM_PATHS):
            continue
        found.append(relative)
    return found


def audit(workspace: Path) -> dict:
    workspace = Path(workspace).resolve()
    root = content_root(workspace)
    if root == workspace:
        return {
            "configured": False,
            "content_root": str(root),
            "entries": [],
            "problems": [],
            "docs_data": [],
            "note": "内容根等于工作区：课程文件本来就在程序目录里，未启用分离检查。",
        }

    lessons = lessons_root(workspace)
    slugs = {item.name for item in lessons.iterdir() if item.is_dir()} if lessons.is_dir() else set()
    entries: list[dict] = []
    for dirpath, dirnames, _filenames in os.walk(workspace):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            candidate = current / name
            if os.path.isjunction(candidate) or os.path.islink(candidate):
                continue  # the path is a link; the bytes live in the content root
            kept.append(name)
        dirnames[:] = kept
        if current.name in slugs:
            relative = current.relative_to(workspace).as_posix()
            reason = _allowed(relative)
            entries.append(
                {
                    "path": relative,
                    "slug": current.name,
                    "allowed": reason is not None,
                    "reason": reason,
                }
            )

    problems = [entry["path"] for entry in entries if not entry["allowed"]]
    return {
        "configured": True,
        "content_root": str(root),
        "lessons": len(slugs),
        "entries": sorted(entries, key=lambda item: item["path"]),
        "problems": problems,
        "docs_data": docs_data_files(workspace),
        "note": None,
    }


def _allowed(relative: str) -> str | None:
    for path, reason in ALLOWED.items():
        if relative == path or relative.startswith(path + "/"):
            return reason
    return None
