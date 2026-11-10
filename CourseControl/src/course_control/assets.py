"""Controlled asset addressing.

A production asset may live inside the workspace or in a configured external
library (BGM, TTS runtime, voice references).  A bare absolute path is not a
contract: it cannot be moved, re-checked, or packaged.  Every reference is
therefore described with a stable asset id, a SHA-256, an origin, and - when
known - a licence status.

The delivery package bundles external assets so it can be replayed on another
machine.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

ROOTS = {
    "bgm_root": "bgm",
    "ai_root": "ai",
    "workspace": "workspace",
}


class AssetError(RuntimeError):
    pass


def _load_local_paths(workspace: Path) -> dict:
    path = workspace / "config" / "local-paths.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _relative_to(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _roots(workspace: Path) -> list[tuple[str, Path]]:
    local = _load_local_paths(workspace)
    roots: list[tuple[str, Path]] = [("workspace", workspace.resolve())]
    for key, prefix in (("bgm_root", "bgm"), ("ai_root", "ai")):
        value = local.get(key)
        if value:
            roots.append((prefix, Path(str(value))))
    tts = local.get("tts") or {}
    runtime = tts.get("runtime_dir")
    if runtime:
        roots.append(("tts-runtime", Path(str(runtime))))
    return roots


def describe_asset(
    workspace: Path,
    value: str | Path,
    *,
    license_status: str | None = None,
    attribution: str | None = None,
) -> dict:
    """Describe an asset reference without copying it.

    ``asset_id`` is stable for a configured root; a path outside every root is
    still recorded but marked ``external`` so the package step can bundle it.
    """
    workspace = workspace.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = (workspace / path).resolve()
    origin = "external"
    asset_id = "external:" + path.as_posix()
    for prefix, root in _roots(workspace):
        relative = _relative_to(path, root)
        if relative is not None:
            origin = prefix
            asset_id = f"{prefix}:{relative}"
            break
    if path.name.startswith("my_voice") or "prompts" in path.parts:
        # Voice references are machine-local by design; the id stays readable.
        if origin == "external":
            origin = "voice-ref"
            asset_id = f"voice-ref:{path.name}"
    return {
        "asset_id": asset_id,
        "path": str(path),
        "origin": origin,
        "exists": path.is_file(),
        "sha256": _sha256(path) if path.is_file() else None,
        "license_status": license_status,
        "attribution": attribution,
    }


def safe_bundle_name(asset: dict) -> str:
    """A filesystem-safe, collision-free name for a bundled external asset."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(asset["path"]).name).strip("-")
    prefix = hashlib.sha256(asset["path"].encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{stem}"


def collect_referenced_assets(workspace: Path, build_root: Path) -> list[dict]:
    """Every asset referenced by build artifacts, with origin and hash."""
    import json

    workspace = workspace.resolve()
    found: dict[str, dict] = {}

    def add(asset: dict) -> None:
        if asset["path"] not in found:
            found[asset["path"]] = asset

    mix_path = build_root / "audio" / "mix.json"
    if mix_path.is_file():
        try:
            mix = json.loads(mix_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            mix = {}
        asset = mix.get("source_asset")
        if not asset and mix.get("source_track"):
            asset = describe_asset(workspace, mix["source_track"])
        if asset:
            add(asset)

    meta_path = build_root / "narration" / "narration.meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        for segment in meta.get("segments") or []:
            value = segment.get("voice_ref")
            if value:
                add(describe_asset(workspace, value))

    return [found[key] for key in sorted(found)]


def collect_external_assets(workspace: Path, build_root: Path) -> list[dict]:
    """Assets outside configured roots that a package must bundle."""
    return [
        asset
        for asset in collect_referenced_assets(workspace, build_root)
        if asset["origin"] in {"external", "voice-ref"}
    ]


__all__ = [
    "AssetError",
    "collect_external_assets",
    "collect_referenced_assets",
    "describe_asset",
    "safe_bundle_name",
]
