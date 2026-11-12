"""V1-D: adapt existing session evidence to ``EvidenceManifestV1``.

The session runners still write the v1 ``evidence.json`` shape with bare
relative paths. This adapter upgrades those paths to ``AssetRef`` records,
adds ``lesson_id`` / ``run_id``, and preserves the old manifest under
``legacy``. It does not re-run a session and never turns a missing artifact
into a pass.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .contracts_v1 import EvidenceEnvironment, EvidenceManifestV1
from .media import asset_ref
from .session import EvidenceManifest, load_session_spec
from .workspace_layout import build_root_for


class V1EvidenceError(RuntimeError):
    """Existing session evidence cannot be represented as V1 evidence."""


def _run_id(spec_path: Path, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()[:8]
    return f"{stamp}-{digest}"


def _required(build_root: Path, value: str | None, label: str) -> Path:
    if not value:
        raise V1EvidenceError(f"{label} is missing from evidence.json")
    path = build_root / value
    if not path.is_file():
        raise V1EvidenceError(f"{label} not found: {path}")
    return path


def adapt_session_evidence(
    spec_path: Path,
    workspace: Path,
    *,
    run_id: str | None = None,
    build_root: Path | None = None,
    now: datetime | None = None,
) -> EvidenceManifestV1:
    spec_path = Path(spec_path).resolve()
    workspace = Path(workspace).resolve()
    spec = load_session_spec(spec_path)
    build_root = (
        Path(build_root).resolve()
        if build_root is not None
        else build_root_for(workspace, spec.lesson) / "code" / spec.shot_id
    )
    evidence_path = build_root / "evidence.json"
    if not evidence_path.is_file():
        raise V1EvidenceError(f"evidence.json not found: {evidence_path}")
    old = EvidenceManifest.model_validate_json(
        evidence_path.read_text(encoding="utf-8")
    )

    execution_path = _required(build_root, old.execution_result, "execution_result")
    recording_inferred = False
    if old.recording_result:
        recording_path = _required(build_root, old.recording_result, "recording_result")
    else:
        candidate = build_root / "recording.json"
        video = build_root / "session.mp4"
        if not (candidate.is_file() and video.is_file()):
            raise V1EvidenceError("recording_result is missing from evidence.json")
        recording_path = candidate
        recording_inferred = True
    validation_path = _required(build_root, old.validation_report, "validation_report")

    transcript_path: Path | None = None
    if old.transcript:
        candidate = build_root / old.transcript
        if candidate.is_file():
            transcript_path = candidate
    if transcript_path is None:
        candidate = build_root / "work" / "transcript.log"
        if candidate.is_file():
            transcript_path = candidate

    artifacts = []
    for relative in old.artifacts:
        path = build_root / relative
        if not path.is_file():
            raise V1EvidenceError(f"declared artifact not found: {path}")
        kind = "video" if path.suffix.lower() in {".mp4", ".mov", ".webm"} else "log"
        artifacts.append(asset_ref(path, workspace, kind, "generated"))

    environment = None
    if spec.environment is not None:
        environment = EvidenceEnvironment(
            kind=spec.environment.kind,
            image=spec.environment.image,
            os=None,
            tool_versions={},
        )

    return EvidenceManifestV1(
        lesson_id=spec.lesson,
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        run_id=run_id or _run_id(spec_path, now),
        spec=asset_ref(spec_path, workspace, "json", "author"),
        environment=environment,
        execution_result=asset_ref(execution_path, workspace, "json", "generated"),
        recording_result=asset_ref(recording_path, workspace, "json", "generated"),
        validation_report=asset_ref(validation_path, workspace, "json", "generated"),
        transcript=(
            asset_ref(transcript_path, workspace, "log", "generated")
            if transcript_path is not None
            else None
        ),
        artifacts=artifacts,
        cache_key=old.cache_key,
        legacy={
            "old_manifest": old.model_dump(mode="json"),
            "recording_result_inferred": recording_inferred,
        },
    )


__all__ = ["V1EvidenceError", "adapt_session_evidence"]
