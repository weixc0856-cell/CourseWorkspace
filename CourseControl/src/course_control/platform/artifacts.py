"""ArtifactRegistry: one index of what a project produced, where it lives and
what it was built from.

The registry does not replace the delivery manifest.  The manifest says what is
delivered; the registry says what exists inside the build, which stage produced
it and which artifacts it consumed.  It is rebuildable from the build tree, so a
lost or corrupt index costs a scan, not data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.platform.atomic import write_json_atomic
from course_control.platform.workspace_layout import runtime_root

ArtifactKind = Literal[
    "source",
    "knowledge",
    "plan",
    "script",
    "scene",
    "media",
    "report",
    "package",
    "other",
]

KIND_BY_SUFFIX = {
    ".mp4": "media",
    ".mov": "media",
    ".webm": "media",
    ".wav": "media",
    ".mp3": "media",
    ".png": "media",
    ".jpg": "media",
    ".jpeg": "media",
    ".json": "report",
    ".md": "report",
    ".yaml": "plan",
    ".yml": "plan",
    ".srt": "script",
    ".vtt": "script",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


class ArtifactEntry(StrictModel):
    id: str
    kind: ArtifactKind = "other"
    path: str
    sha256: str
    bytes: int = 0
    produced_by: str = "unknown"
    inputs: list[str] = []
    created_at: str = ""
    status: Literal["present", "missing"] = "present"


class ArtifactRegistry(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    artifacts: list[ArtifactEntry] = []


def registry_path(workspace: Path, project_id: str) -> Path:
    return runtime_root(workspace) / "artifacts" / project_id / "registry.json"


def load_registry(path: Path) -> ArtifactRegistry | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return ArtifactRegistry.model_validate(data)


def save_registry(registry: ArtifactRegistry, path: Path) -> Path:
    write_json_atomic(path, registry.model_dump(mode="json"))
    return path


def _entry_id(relative: str) -> str:
    clean = relative.replace("\\", "/").strip("/")
    return "art." + clean.replace("/", ".").replace(" ", "_")


def entry_for_file(
    path: Path,
    base: Path,
    *,
    produced_by: str = "unknown",
    inputs: list[str] | None = None,
) -> ArtifactEntry:
    relative = path.resolve().relative_to(base.resolve()).as_posix()
    return ArtifactEntry(
        id=_entry_id(relative),
        kind=KIND_BY_SUFFIX.get(path.suffix.lower(), "other"),
        path=relative,
        sha256=sha256_file(path) or "",
        bytes=path.stat().st_size if path.is_file() else 0,
        produced_by=produced_by,
        inputs=list(inputs or []),
        created_at=_now(),
    )


def register(registry: ArtifactRegistry, entry: ArtifactEntry) -> ArtifactRegistry:
    """Insert or replace one entry by id; registration is idempotent."""
    artifacts = [item for item in registry.artifacts if item.id != entry.id]
    artifacts.append(entry)
    return registry.model_copy(update={"artifacts": sorted(artifacts, key=lambda item: item.id)})


def find(registry: ArtifactRegistry, artifact_id: str) -> ArtifactEntry | None:
    for item in registry.artifacts:
        if item.id == artifact_id:
            return item
    return None


def rebuild_from_build(
    build_root: Path,
    project_id: str,
    *,
    produced_by: str = "build",
) -> ArtifactRegistry:
    """Recreate the index by scanning a build tree."""
    artifacts: list[ArtifactEntry] = []
    if build_root.is_dir():
        for path in sorted(build_root.rglob("*")):
            if not path.is_file():
                continue
            entry = entry_for_file(path, build_root, produced_by=produced_by)
            if entry.sha256:
                artifacts.append(entry)
    return ArtifactRegistry(project_id=project_id, artifacts=artifacts)


def mark_missing(registry: ArtifactRegistry, build_root: Path) -> ArtifactRegistry:
    """Flag entries whose files disappeared; never delete the record."""
    artifacts = []
    for entry in registry.artifacts:
        exists = (build_root / entry.path).is_file()
        artifacts.append(
            entry.model_copy(update={"status": "present" if exists else "missing"})
        )
    return registry.model_copy(update={"artifacts": artifacts})


__all__ = [
    "ArtifactEntry",
    "ArtifactRegistry",
    "registry_path",
    "load_registry",
    "save_registry",
    "entry_for_file",
    "register",
    "find",
    "rebuild_from_build",
    "mark_missing",
    "sha256_file",
]
