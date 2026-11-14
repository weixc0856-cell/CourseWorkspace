"""Stdlib-only build manifest and cache keys for asset scenes.

This module is imported by two different Pythons:

* CourseControl tests (Python 3.12, pydantic available);
* Blender 5.2's bundled Python (3.13, no pydantic).

It therefore uses only the standard library.  The builder loads it by file path
so importing it never pulls in the pydantic scene-spec models.

A manifest answers one question: which exact inputs produced this render?
It is written before rendering (status=running), updated after success or
failure, and reused only when every input hash and render parameter matches.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUILDER_VERSION = "0.2.0"
MANIFEST_SCHEMA_VERSION = 1


class ManifestError(RuntimeError):
    def __init__(self, message: str, manifest_path: Path | None = None):
        super().__init__(message)
        self.manifest_path = manifest_path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_path(path: Path) -> dict[str, Any]:
    """Hash a file, or a directory tree including relative file names."""
    path = Path(path)
    if path.is_file():
        return {
            "path": str(path.resolve()),
            "sha256": _hash_file(path),
            "hash_kind": "file",
            "files": 1,
        }
    if path.is_dir():
        digest = hashlib.sha256()
        files = 0
        for item in sorted(p for p in path.rglob("*") if p.is_file()):
            relative = item.relative_to(path).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(bytes.fromhex(_hash_file(item)))
            files += 1
        if files == 0:
            raise ManifestError(f"asset directory is empty: {path}")
        return {
            "path": str(path.resolve()),
            "sha256": digest.hexdigest(),
            "hash_kind": "directory",
            "files": files,
        }
    raise ManifestError(f"asset path does not exist: {path}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"expected a JSON object: {path}")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path


def log_line(log_path: Path | None, message: str) -> None:
    line = f"{now_iso()} {message}\n"
    print(line.rstrip())
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _asset_root(spec_path: Path, spec: dict[str, Any]) -> Path:
    return Path(str(spec.get("asset_root") or spec_path.parent.parent)).resolve()


def _library_path(spec_path: Path, spec: dict[str, Any]) -> Path:
    return _asset_root(spec_path, spec) / "library.json"


def _load_library(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    return {
        str(item["id"]): item
        for item in data.get("assets", [])
        if isinstance(item, dict) and item.get("id")
    }


def _asset_path(asset: dict[str, Any], root: Path) -> Path:
    path = Path(str(asset.get("path") or ""))
    return path if path.is_absolute() else root / path


def _referenced_ids(spec: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if spec.get("hdri"):
        ids.append(str(spec["hdri"]))
    terrain = spec.get("terrain") or {}
    for key in ("material", "heightmap"):
        value = terrain.get(key)
        if value:
            # Either a library id or a direct path; add_asset handles both.
            ids.append(str(value))
    for item in spec.get("objects") or []:
        if isinstance(item, dict) and item.get("asset"):
            ids.append(str(item["asset"]))
    return list(dict.fromkeys(ids))


def collect_inputs(
    spec_path: Path,
    spec: dict[str, Any],
    builder_path: Path,
    library_path: Path | None = None,
    blender_version: str | None = None,
    addons: list[dict[str, Any]] | None = None,
    grammar_path: Path | None = None,
) -> dict[str, Any]:
    spec_path = Path(spec_path).resolve()
    root = _asset_root(spec_path, spec)
    library_file = Path(library_path).resolve() if library_path else _library_path(spec_path, spec)
    library = _load_library(library_file)
    inputs: dict[str, Any] = {
        "shot_spec": hash_path(spec_path),
        "library": hash_path(library_file),
        "builder": hash_path(Path(builder_path).resolve()),
        "assets": [],
    }
    environment = spec.get("environment_spec")
    if environment:
        inputs["environment_spec"] = hash_path(Path(str(environment)).resolve())

    seen: set[str] = set()

    def add_asset(asset_id: str) -> None:
        if asset_id in seen:
            return
        seen.add(asset_id)
        asset = library.get(asset_id)
        if asset is None:
            # A direct heightmap path is allowed by the builder when it is not
            # a library id; hash the file instead of silently dropping it.
            direct = Path(asset_id)
            if not direct.is_absolute():
                direct = root / direct
            if direct.exists():
                inputs["assets"].append({"id": asset_id, **hash_path(direct)})
                return
            raise ManifestError(f"asset not in library: {asset_id}")
        path = _asset_path(asset, root)
        # A glTF is not a complete asset: its .bin and textures live beside it.
        # Hash the model's directory so those dependencies enter the cache key.
        hash_target = path.parent if asset.get("kind") == "model" else path
        entry = {
            "id": asset_id,
            "kind": asset.get("kind"),
            "version": asset.get("version", 1),
            "quality_level": asset.get("quality_level", "standard"),
            "license": asset.get("license"),
            **hash_path(hash_target),
        }
        entry["path"] = str(path)
        inputs["assets"].append(entry)
        for dependency in asset.get("dependencies") or []:
            add_asset(str(dependency))

    for asset_id in _referenced_ids(spec):
        # A heightmap may be a direct path; add_asset handles both forms.
        add_asset(asset_id)

    inputs["assets"].sort(key=lambda item: str(item.get("id")))
    if blender_version:
        inputs["blender"] = {"version": blender_version}
    if addons is not None:
        inputs["addons"] = addons
    if grammar_path is not None and Path(grammar_path).is_file():
        inputs["visual_grammar_file"] = hash_path(Path(grammar_path))
    return inputs


def _render_signature(render: dict[str, Any], out: Path) -> dict[str, Any]:
    width, height = render.get("resolution", [1080, 1920])
    return {
        "engine": render.get("engine", "CYCLES"),
        "samples": int(render.get("samples", 40)),
        "resolution": [int(width), int(height)],
        "frames": int(render.get("frames", 1)),
        "frame_range": [1, int(render.get("frames", 1))],
        "fps": int(render.get("fps", 30)),
        "profile": render.get("profile"),
        "passes": list(render.get("passes") or []),
        "output": str(Path(out).resolve()),
    }


def cache_key(
    inputs: dict[str, Any],
    render: dict[str, Any],
    out: Path,
    builder_version: str,
    visual_grammar: str | None,
    seed: int = 0,
) -> str:
    payload = {
        "inputs": inputs,
        "render": _render_signature(render, out),
        "builder_version": builder_version,
        "visual_grammar": visual_grammar,
        "seed": seed,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _environment_path(spec: dict[str, Any]) -> str | None:
    value = spec.get("environment_spec") or spec.get("environment")
    if not value:
        return None
    return str(Path(str(value)).resolve())


def _project_name(spec_path: Path, spec: dict[str, Any]) -> str:
    if spec.get("project"):
        return str(spec["project"])
    parts = spec_path.parts
    if "kits" in parts:
        index = parts.index("kits")
        if index + 1 < len(parts):
            return parts[index + 1]
    return "default"


@dataclass
class PrepareResult:
    manifest: dict[str, Any]
    manifest_path: Path
    log_path: Path
    cache_hit: bool = False
    cached_manifest: Path | None = None


def _manifest_dir(out: Path, manifest_dir: Path | None) -> Path:
    return Path(manifest_dir).resolve() if manifest_dir else (out.parent / "manifests").resolve()


def find_cached(manifest_dir: Path, key: str, out: Path, shot: str) -> Path | None:
    directory = Path(manifest_dir)
    if not directory.is_dir():
        return None
    matches: list[tuple[str, Path]] = []
    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "pass":
            continue
        if data.get("cache_key") != key or str(data.get("shot")) != shot:
            continue
        output = Path(str(data.get("output") or ""))
        try:
            if output.resolve() != Path(out).resolve() or output.stat().st_size <= 0:
                continue
        except OSError:
            continue
        matches.append((str(data.get("finished_at") or ""), path))
    if not matches:
        return None
    return sorted(matches)[-1][1]


def prepare(
    *,
    spec_path: Path,
    spec: dict[str, Any],
    render: dict[str, Any],
    out: Path,
    builder_path: Path,
    builder_version: str = BUILDER_VERSION,
    blender_version: str | None = None,
    python_version: str | None = None,
    addons: list[dict[str, Any]] | None = None,
    library_path: Path | None = None,
    manifest_dir: Path | None = None,
    use_cache: bool = True,
    visual_grammar: str | None = None,
    grammar_path: Path | None = None,
    seed: int = 0,
) -> PrepareResult:
    out = Path(out).resolve()
    spec_path = Path(spec_path).resolve()
    manifest_dir = _manifest_dir(out, manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    shot = str(spec.get("id") or spec_path.stem)
    started = now_iso()
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "build_id": "",
        "project": _project_name(spec_path, spec),
        "shot": shot,
        "environment": _environment_path(spec),
        "builder_version": builder_version,
        "blender_version": blender_version,
        "python_version": python_version,
        "addons": addons or [],
        "visual_grammar": visual_grammar,
        "render_profile": render.get("profile"),
        "render": _render_signature(render, out),
        "seed": seed,
        "inputs": {},
        "status": "running",
        "error": None,
        "started_at": started,
        "finished_at": None,
        "elapsed_s": None,
        "output": str(out),
        "temp_output": None,
        "log": None,
    }
    try:
        inputs = collect_inputs(
            spec_path,
            spec,
            builder_path,
            library_path=library_path,
            blender_version=blender_version,
            addons=addons,
            grammar_path=grammar_path,
        )
    except Exception as exc:  # noqa: BLE001 - the manifest records the reason
        manifest.update({"status": "fail", "error": str(exc), "finished_at": now_iso()})
        manifest["build_id"] = f"{_stamp()}-{shot}-failed"
        manifest_path = manifest_dir / f"{shot}-{manifest['build_id']}.json"
        write_json_atomic(manifest_path, manifest)
        raise ManifestError(str(exc), manifest_path) from exc

    key = cache_key(inputs, render, out, builder_version, visual_grammar, seed)
    build_id = f"{_stamp()}-{shot}-{key[:6]}"
    manifest.update({
        "build_id": build_id,
        "cache_key": key,
        "inputs": inputs,
    })
    log_path = manifest_dir / f"{shot}-{build_id}.log"
    manifest["log"] = str(log_path)
    manifest_path = manifest_dir / f"{shot}-{build_id}.json"
    cached = find_cached(manifest_dir, key, out, shot) if use_cache else None
    if cached is not None:
        return PrepareResult(
            manifest=manifest,
            manifest_path=manifest_path,
            log_path=log_path,
            cache_hit=True,
            cached_manifest=cached,
        )
    write_json_atomic(manifest_path, manifest)
    return PrepareResult(manifest=manifest, manifest_path=manifest_path, log_path=log_path)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def finalize(
    manifest_path: Path,
    *,
    status: str,
    output: Path | None = None,
    temp_output: Path | None = None,
    elapsed_s: float | None = None,
    error: str | None = None,
) -> Path:
    manifest_path = Path(manifest_path)
    data = load_json(manifest_path)
    data.update({
        "status": status,
        "finished_at": now_iso(),
        "elapsed_s": round(elapsed_s, 3) if elapsed_s is not None else data.get("elapsed_s"),
        "error": error,
    })
    if output is not None:
        data["output"] = str(Path(output).resolve())
    if temp_output is not None:
        data["temp_output"] = str(Path(temp_output).resolve())
    write_json_atomic(manifest_path, data)
    return manifest_path


def start_clock() -> float:
    return time.time()
