"""The lesson that local integration tests run against.

Tracked code must not name a course. These tests therefore take their lesson
from a local, gitignored file (``local-lesson.yaml`` next to this module) or
from ``COURSEWORKSPACE_LOCAL_LESSON``. A clean clone has neither, and every
test that depends on it skips.

    # CourseControl/tests/local-lesson.yaml  (not committed)
    lesson: <slug of a lesson under <content root>/lessons>
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from course_control.platform.workspace_layout import lessons_root

WORKSPACE = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("local-lesson.yaml")
ENV = "COURSEWORKSPACE_LOCAL_LESSON"


@dataclass(frozen=True)
class LocalLesson:
    name: str
    path: Path


def local_lesson() -> LocalLesson | None:
    name = os.environ.get(ENV)
    if not name and CONFIG.is_file():
        try:
            data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
            name = str(data.get("lesson") or "") or None
        except (OSError, yaml.YAMLError):
            name = None
    if not name:
        return None
    path = lessons_root(WORKSPACE) / name
    return LocalLesson(name=name, path=path) if path.is_dir() else None


LOCAL = local_lesson()
REASON = f"no local lesson configured ({CONFIG.name} or {ENV})"
