"""Load approved authoring artifacts for the director layer."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ..authoring.models import ApprovalFile, Brief, NarrationScript, Outline
from ..paths import ContractError, LessonPaths, format_validation_error
from .schema import ApprovalArtifact, ApprovalState

REQUIRED_APPROVALS = ("brief", "outline", "script")


@dataclass
class DirectorInputs:
    paths: LessonPaths
    brief: Brief
    outline: Outline
    script: NarrationScript
    approval: ApprovalState


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, model):
    if not path.is_file():
        raise ContractError(f"authoring file not found: {path}")
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ContractError(format_validation_error(exc, str(path))) from exc


def resolve_approval(lesson_dir: Path, auth) -> ApprovalState:
    approval_path = lesson_dir / (auth.approval or "authoring/approval.json")
    file = ApprovalFile() if not approval_path.is_file() else ApprovalFile.model_validate_json(
        approval_path.read_text(encoding="utf-8")
    )
    artifacts: list[ApprovalArtifact] = []
    for kind in REQUIRED_APPROVALS:
        relative = getattr(auth, kind, None)
        if not relative:
            artifacts.append(ApprovalArtifact(kind=kind, path="", status="unapproved"))
            continue
        path = lesson_dir / relative
        entry = file.find(relative)
        if entry is None:
            artifacts.append(ApprovalArtifact(kind=kind, path=relative, status="unapproved"))
            continue
        if not path.is_file():
            artifacts.append(ApprovalArtifact(kind=kind, path=relative, status="missing"))
            continue
        digest = _sha256(path)
        status = "ok" if digest == entry.sha256 else "mismatch"
        artifacts.append(
            ApprovalArtifact(
                kind=kind,
                path=relative,
                status=status,
                sha256=digest,
                approved_at=entry.approved_at,
            )
        )
    approved = all(item.status == "ok" for item in artifacts)
    return ApprovalState(approved=approved, artifacts=artifacts)


def load_inputs(workspace: Path, lesson_dir: Path) -> DirectorInputs:
    paths = LessonPaths.load(workspace, lesson_dir)
    auth = paths.lesson.authoring
    if auth is None:
        raise ContractError("lesson.authoring is required for the director layer")
    for name in REQUIRED_APPROVALS:
        if not getattr(auth, name, None):
            raise ContractError(f"lesson.authoring.{name} is required")

    brief = _load_json(paths.content_path(auth.brief), Brief)
    outline = _load_json(paths.content_path(auth.outline), Outline)
    script = _load_json(paths.content_path(auth.script), NarrationScript)
    if brief.lesson != paths.slug or outline.lesson != paths.slug or script.lesson != paths.slug:
        raise ContractError("authoring lesson ids must match lesson.yaml lesson_id")
    approval = resolve_approval(paths.lesson_dir, auth)
    return DirectorInputs(paths=paths, brief=brief, outline=outline, script=script, approval=approval)
