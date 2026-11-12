"""Voice Bible: the approved identity of one narrator's voice.

A bible fixes everything that must stay constant across a series: the
reference recording (by hash, not by path), the prompt text, the language, the
synthesis mode and the pacing.  Lessons point at a bible by id; changing the
bible changes every narration that uses it, which is exactly what should
happen when the voice itself changes.

Identity is the SHA-256 of the document, so a voice survives moving the
content root, renaming a folder or copying the series elsewhere.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator

from course_control.content.contracts import SLUG_RE, StrictModel


class AudioAssetError(RuntimeError):
    """A voice bible or lexicon is missing or unusable."""


class ApprovedSample(StrictModel):
    path: str
    sha256: str | None = None
    note: str | None = None


class VoiceBible(StrictModel):
    schema_version: Literal[1] = 1
    id: str
    language: str = Field(default="en", min_length=2, max_length=16)
    ref_audio: str
    # Declared by hand; when present it is verified, when absent it is recorded.
    ref_audio_sha256: str | None = None
    prompt_text: str = ""
    backend: Literal["voxcpm2"] = "voxcpm2"
    model: str = "VoxCPM2"
    mode: Literal["reference_only", "prompt_reference"] = "reference_only"
    speed: float = Field(default=1.0, gt=0.5, le=2.0)
    text_frontend: bool = True
    style: str | None = None
    approved_samples: list[ApprovedSample] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("voice bible id must be a slug")
        return value

    @field_validator("ref_audio")
    @classmethod
    def _ref_audio_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ref_audio must not be blank")
        return value


def load(path: Path) -> VoiceBible:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AudioAssetError(f"cannot read voice bible {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AudioAssetError(f"voice bible {path} is not a mapping")
    try:
        return VoiceBible.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - surface pydantic's message verbatim
        raise AudioAssetError(f"invalid voice bible {path}: {exc}") from exc


def resolve(root: Path, ident: str) -> Path:
    """``<content_root>/audio/voice-bibles/<id>.yaml``."""
    return (Path(root) / "voice-bibles" / f"{ident}.yaml").resolve()


def ref_audio_path(bible: VoiceBible, source: Path) -> Path:
    """Resolve ``ref_audio`` next to the bible itself; absolute paths pass through."""
    candidate = Path(bible.ref_audio).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path(source).parent / candidate).resolve()


def digest(bible: VoiceBible) -> str:
    payload = json.dumps(bible.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check(bible: VoiceBible, source: Path) -> list[str]:
    problems: list[str] = []
    audio = ref_audio_path(bible, source)
    if not audio.is_file():
        problems.append(f"ref_audio not found: {audio}")
        return problems
    if bible.ref_audio_sha256:
        actual = _sha(audio)
        if actual != bible.ref_audio_sha256.lower():
            problems.append(
                f"ref_audio sha256 mismatch: declared {bible.ref_audio_sha256[:12]}…, "
                f"file is {actual[:12]}…"
            )
    if bible.mode == "prompt_reference" and not bible.prompt_text.strip():
        problems.append("mode prompt_reference requires prompt_text")
    for sample in bible.approved_samples:
        path = Path(sample.path)
        if not path.is_absolute():
            path = Path(source).parent / path
        if not path.is_file():
            problems.append(f"approved sample not found: {path}")
        elif sample.sha256 and _sha(path) != sample.sha256.lower():
            problems.append(f"approved sample sha256 mismatch: {path.name}")
    return problems


def _sha(path: Path) -> str:
    digest_value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest_value.update(chunk)
    return digest_value.hexdigest()
