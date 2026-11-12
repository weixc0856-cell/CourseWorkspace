"""Picture Lock: the picture the edit was approved against.

A lock is a snapshot, not a veto.  It records what was on screen when someone
approved it; changing anything afterwards is allowed and simply shows up as a
difference next time ``lock-status`` runs.

It captures four things:

* the picture units and the SHA-256 of each file that plays;
* the shot-sheet version it was locked against, plus each shot's design
  fingerprint;
* the scenes and assets the shots depend on;
* the review record (who approved it, and their note).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..animatic import AnimaticError
from ..animatic import resolve as resolve_units
from ..authoring import shot_sheet
from ..media import sha256_file
from ..paths import LessonPaths
from .dependencies import LockError

LOCK_NAME = "picture.lock.json"


def snapshot(paths: LessonPaths) -> dict:
    try:
        timeline = resolve_units(paths)
    except AnimaticError as exc:
        raise LockError(f"no picture timeline yet: {exc}") from exc

    sheet = shot_sheet.compile_sheet(paths)
    hashes: dict[str, str] = {}
    pictures: list[dict] = []
    for unit in timeline.units:
        digest = _sha(unit.source)
        hashes[f"picture:{unit.id}"] = digest
        pictures.append(
            {
                "id": unit.id,
                "kind": unit.kind,
                "source": unit.source_rel,
                "start_s": round(unit.start_s, 3),
                "duration_s": round(unit.duration_s, 3),
                "sha256": digest,
            }
        )

    hashes["shot_sheet"] = sheet["source"]["sha256"] or ""
    for shot in sheet["shots"]:
        hashes[f"sheet:{shot['id']}"] = shot["fingerprint"]
        scene = _scene_hash(paths, shot)
        if scene is not None:
            hashes[f"scene:{shot['id']}"] = scene
        for asset in shot["assets"]:
            hashes[f"asset:{asset['ref']}"] = asset["sha256"] or ""

    checks: list[dict] = []
    missing = [item["id"] for item in pictures if item["kind"] == "placeholder"]
    checks.append(
        {
            "id": "pictures",
            "status": "pass" if not missing else "fail",
            "detail": None if not missing else ", ".join(missing[:8]),
        }
    )
    checks.append(
        {
            "id": "sheet_version",
            "status": "pass" if sheet["source"]["schema_version"] >= 2 else "warn",
            "detail": None
            if sheet["source"]["schema_version"] >= 2
            else "shot sheet is schema v1: no design fingerprints",
        }
    )
    absent = [
        asset["ref"]
        for shot in sheet["shots"]
        for asset in shot["assets"]
        if not asset["found"]
    ]
    checks.append(
        {
            "id": "assets",
            "status": "pass" if not absent else "fail",
            "detail": None if not absent else ", ".join(sorted(set(absent))),
        }
    )

    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "kind": "picture",
        "sheet": sheet["source"],
        "pictures": pictures,
        "hashes": hashes,
        "checks": checks,
    }


def write(
    paths: LessonPaths,
    *,
    approved_by: str | None = None,
    note: str | None = None,
) -> dict:
    lock = snapshot(paths)
    lock["locked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lock["review"] = {"approved_by": approved_by, "note": note}
    if not approved_by:
        lock["checks"].append(
            {
                "id": "review_recorded",
                "status": "warn",
                "detail": "no --approved-by: the lock has no review record",
            }
        )
    path = lock_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": path, "lock": lock}


def load(paths: LessonPaths) -> dict | None:
    path = lock_path(paths)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"picture lock is unreadable: {path}: {exc}") from exc


def lock_path(paths: LessonPaths) -> Path:
    return paths.build_root / "locks" / LOCK_NAME


def _scene_hash(paths: LessonPaths, shot: dict) -> str | None:
    scene = shot["scene"]
    if "::" in scene:
        scene = scene.split("::", 1)[0]
    try:
        path, _root = paths.resolve_engine_path(shot["engine"], scene)
    except Exception:  # noqa: BLE001 - an unknown engine must not stop the lock
        return None
    return sha256_file(path) if path.is_file() else ""


def _sha(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return sha256_file(path)
