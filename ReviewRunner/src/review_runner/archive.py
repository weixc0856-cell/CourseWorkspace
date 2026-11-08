"""Archive helpers: every run leaves a self-describing, local audit trail."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schema import FindingsEnvelope, Manifest


def write_json(path: Path, data) -> None:
    if hasattr(data, "model_dump"):
        payload = data.model_dump(mode="json")
    else:
        payload = data
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_directory(root: Path) -> dict[str, str]:
    """Hash every file below ``root`` using POSIX-style relative paths."""
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        hashes[rel] = sha256_bytes(path.read_bytes())
    return hashes


def hash_lines(hashes: dict[str, str]) -> str:
    return "".join(f"{digest}  {path}\n" for path, digest in sorted(hashes.items()))


def write_manifest(review_dir: Path, manifest: Manifest) -> Path:
    target = review_dir / "manifest.json"
    write_json(target, manifest)
    return target


def write_findings(review_dir: Path, envelope: FindingsEnvelope) -> Path:
    target = review_dir / "findings.json"
    write_json(target, envelope)
    return target


__all__ = [
    "hash_directory",
    "hash_lines",
    "sha256_bytes",
    "write_bytes",
    "write_findings",
    "write_json",
    "write_manifest",
    "write_text",
]
