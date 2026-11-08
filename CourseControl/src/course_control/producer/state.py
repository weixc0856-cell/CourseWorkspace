"""Production state: hashes, per-shot fingerprints, usage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..director.planners import resolve_scene
from ..director.schema import DirectorPlan
from ..paths import LessonPaths
from .schema import ProductionState, ShotFingerprint, Usage


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def canonical_json(payload) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def state_path(build_root: Path) -> Path:
    return build_root / "production" / "state.json"


def load_state(path: Path) -> ProductionState | None:
    if not path.is_file():
        return None
    return ProductionState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(state: ProductionState, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def build_fingerprints(plan: DirectorPlan, paths: LessonPaths, director_dir: Path) -> list[ShotFingerprint]:
    narration = {segment.id: segment.text for segment in plan.narration}
    fingerprints: list[ShotFingerprint] = []
    for shot in plan.shots:
        scene_file = resolve_scene(paths, shot.engine, shot.scene)
        scene_hash = sha256_file(scene_file) if scene_file is not None and scene_file.is_file() else None
        direction_file = director_dir / "directions" / f"{shot.id}.json"
        direction_hash = sha256_file(direction_file)
        content = {
            "slide": shot.slide,
            "title": shot.title,
            "learning_intent": shot.learning_intent,
            "visual_metaphor": shot.visual_metaphor,
            "target_seconds": shot.target_seconds,
            "cue_seconds": shot.cue_seconds,
            "engine": shot.engine,
            "scene": shot.scene,
            "blend_task": shot.blend_task,
            "layout_template": shot.layout_template,
            "inputs": shot.inputs,
        }
        narration_payload = {sid: narration.get(sid, "") for sid in shot.narration_ids}
        content_hash = sha256_text(canonical_json(content))
        narration_hash = sha256_text(canonical_json(narration_payload))
        combined = sha256_text(
            canonical_json(
                {
                    "content": content_hash,
                    "narration": narration_hash,
                    "scene": scene_hash,
                }
            )
        )
        fingerprints.append(
            ShotFingerprint(
                shot_id=shot.id,
                slide=shot.slide,
                engine=shot.engine,
                scene=shot.scene,
                fingerprint=combined,
                content_sha256=content_hash,
                narration_sha256=narration_hash,
                scene_sha256=scene_hash,
                direction_sha256=direction_hash,
                narration_ids=list(shot.narration_ids),
            )
        )
    return fingerprints


def disk_usage_gb(root: Path) -> float:
    total = 0
    if root.is_dir():
        for path in root.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    return round(total / 1_000_000_000, 3)


def add_usage(state: ProductionState, wall_seconds: float, updated_at: str) -> ProductionState:
    state.usage = Usage(
        wall_seconds=round(state.usage.wall_seconds + wall_seconds, 3),
        api_cost_usd=state.usage.api_cost_usd,
        local_model_calls=state.usage.local_model_calls,
        disk_gb=state.usage.disk_gb,
        updated_at=updated_at,
    )
    return state


def limit_problems(state: ProductionState, order) -> list[str]:
    problems: list[str] = []
    if state.usage.wall_seconds > order.limits.max_wall_seconds:
        problems.append(
            f"wall time {state.usage.wall_seconds:g}s exceeds {order.limits.max_wall_seconds:g}s"
        )
    if state.usage.api_cost_usd > order.limits.max_api_cost_usd:
        problems.append(
            f"API cost ${state.usage.api_cost_usd:g} exceeds ${order.limits.max_api_cost_usd:g}"
        )
    if state.usage.local_model_calls > order.limits.max_local_model_calls:
        problems.append(
            f"local model calls {state.usage.local_model_calls} exceed {order.limits.max_local_model_calls}"
        )
    if state.usage.disk_gb > order.limits.max_disk_gb:
        problems.append(f"disk {state.usage.disk_gb:g} GB exceeds {order.limits.max_disk_gb:g} GB")
    return problems
