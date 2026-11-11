"""Producer orchestration: order -> director plan -> delivery package -> state."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..director.inputs import load_inputs
from ..director.orchestrator import build as build_director
from ..director.schema import DirectorPlan
from ..contracts import Status
from ..paths import ContractError, LessonPaths
from ..pipeline import BuildOptions, run_build
from ..report import toolchain_versions
from ..validators import validate
from .delivery import build_manifest, write_manifest
from ..audio_plan import write_audio_plan
from .order import OrderOverrides, approve, ensure_order, load_order, now, order_path, save_order
from .rebuild import ShotDelta, diff_fingerprints
from .schema import DeliveryManifest, ProductionOrder, ProductionState
from .state import (
    add_usage,
    build_fingerprints,
    disk_usage_gb,
    limit_problems,
    load_state,
    save_state,
    sha256_file,
    state_path,
)


@dataclass
class ProducerResult:
    order: ProductionOrder
    plan: DirectorPlan
    manifest: DeliveryManifest
    state: ProductionState
    paths: dict[str, Path] = field(default_factory=dict)
    deltas: list[ShotDelta] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)


def _write_toolchain(workspace: Path, build_root: Path) -> Path:
    path = build_root / "production" / "toolchain.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = toolchain_versions(workspace)
    except Exception as exc:  # noqa: BLE001 - a missing tool must not abort the package
        payload = {"error": str(exc)}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _coverage_notes(order: ProductionOrder, plan: DirectorPlan) -> list[str]:
    corpus = " ".join(
        f"{chapter.title} {chapter.learning_objective}" for chapter in plan.chapters
    ).lower()
    gaps: list[str] = []
    for item in order.must_cover:
        words = [word for word in re.findall(r"[a-z][a-z-]{4,}", item.lower())]
        if words and not any(word in corpus for word in words):
            gaps.append(f"must-cover has no matching chapter objective: {item}")
    return gaps


def _report(result: ProducerResult, workspace: Path) -> str:
    order = result.order
    manifest = result.manifest
    lines = [
        f"# Production report — {order.lesson_id}",
        "",
        f"- order: `{order.order_id}` ({order.language}, {order.target_seconds:g}s)",
        f"- audience: {order.audience}",
        f"- must cover: {len(order.must_cover)} items",
        f"- must not: {'; '.join(order.must_not) if order.must_not else 'none'}",
        f"- approved by: {order.approved_by or 'pending'}",
        f"- state: **{result.state.status}**",
        f"- director plan: {result.plan.status} ({result.plan.summary.shots} shots, "
        f"{result.plan.summary.ready_shots} ready, {result.plan.summary.planned_shots} planned)",
        f"- delivery: {manifest.status}",
        "",
        "## Stages",
        "",
        "| stage | status |",
        "| --- | --- |",
    ]
    for name, status in result.state.stages.items():
        lines.append(f"| {name} | {status} |")
    lines += [
        "",
        "## Delivery items",
        "",
        "| item | status | files present |",
        "| --- | --- | ---: |",
    ]
    for item in manifest.items:
        present = sum(1 for record in item.files if record.status == "present")
        lines.append(f"| {item.id} {item.title} | {item.status} | {present}/{len(item.files)} |")
    lines += ["", "## Missing", ""]
    lines += [f"- {entry}" for entry in manifest.missing] or ["- none"]
    lines += [
        "",
        "## Usage",
        "",
        f"- wall: {result.state.usage.wall_seconds:g}s / {order.limits.max_wall_seconds:g}s",
        f"- API cost: ${result.state.usage.api_cost_usd:g} / ${order.limits.max_api_cost_usd:g}",
        f"- local model calls: {result.state.usage.local_model_calls} / {order.limits.max_local_model_calls}",
    ]
    if result.limits:
        lines += ["", "## Limit violations", ""] + [f"- {item}" for item in result.limits]
    if result.state.notes:
        lines += ["", "## Coverage notes", ""] + [f"- {item}" for item in result.state.notes]
    lines += ["", "## Artifacts", ""]
    for name, path in result.paths.items():
        try:
            display = path.resolve().relative_to(workspace.resolve()).as_posix()
        except ValueError:
            display = path.as_posix()
        lines.append(f"- {name}: `{display}`")
    lines += ["", "## Changed since last run", ""]
    if result.deltas:
        for delta in result.deltas:
            lines.append(f"- {delta.shot_id}: {delta.change} ({'; '.join(delta.reasons)})")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Policy",
        "",
        "- The producer never reads credentials; authorizations are declarative in the order.",
        "- Missing required artifacts stay blocked; they are never reported as passed.",
        "",
    ]
    return "\n".join(lines)


def run(
    workspace: Path,
    lesson_dir: Path,
    build_root: Path | None = None,
    overrides: OrderOverrides | None = None,
    force_order: bool = False,
    approve_by: str | None = None,
) -> ProducerResult:
    started = time.monotonic()
    workspace = workspace.resolve()
    inputs = load_inputs(workspace, lesson_dir)
    root = (build_root or inputs.paths.build_root).resolve()

    order, path = ensure_order(inputs, root, overrides, force_order)
    if approve_by:
        approve(order, approve_by)
        save_order(order, path)

    validation = validate(inputs.paths)
    plan, director_paths = build_director(workspace, lesson_dir, root / "director")
    _write_toolchain(workspace, root)
    audio_plan, audio_path = write_audio_plan(root, inputs.paths.lesson)

    previous = load_state(state_path(root))
    state = previous or ProductionState(
        lesson_id=inputs.paths.slug, order_id=order.order_id, updated_at=now()
    )
    state.order_id = order.order_id
    state.updated_at = now()
    save_state(state, state_path(root))

    manifest = build_manifest(order, plan, inputs.paths, root, workspace)
    delivery_paths = write_manifest(manifest, order, root)
    state.director_plan_sha256 = sha256_file(director_paths["plan"])
    current = build_fingerprints(plan, inputs.paths, root / "director")
    deltas = diff_fingerprints(previous.shots, current) if previous else []
    state.shots = current
    state.delivery_status = manifest.status
    state.stages = {
        "validate": "pass" if validation.ok else "fail",
        "director": plan.status,
        "render": "present" if (root / "final" / "course-video.mp4").is_file() else "missing",
        "audio": "present" if (root / "narration" / "narration.wav").is_file() else "missing",
        "audio_policy": audio_plan.status,
        "delivery": manifest.status,
    }
    add_usage(state, time.monotonic() - started, now())
    state.usage.disk_gb = disk_usage_gb(root)
    notes = _coverage_notes(order, plan)
    if audio_plan.errors:
        notes.extend(f"audio policy: {error}" for error in audio_plan.errors)
    if order.language != inputs.script.language:
        notes.append(f"order language {order.language} differs from script language {inputs.script.language}")
    if abs(order.target_seconds - plan.duration.target_seconds) > plan.duration.tolerance_seconds:
        notes.append(
            f"order target {order.target_seconds:g}s differs from director target {plan.duration.target_seconds:g}s"
        )
    state.notes = notes
    limits = limit_problems(state, order)
    if not validation.ok or limits or audio_plan.status == "blocked":
        state.status = "blocked"
    elif manifest.status == "delivered":
        state.status = "delivered"
    elif manifest.status == "awaiting_approval":
        state.status = "awaiting_approval"
    else:
        state.status = "blocked"
    state_file = save_state(state, state_path(root))

    result = ProducerResult(
        order=order,
        plan=plan,
        manifest=manifest,
        state=state,
        paths={
            "order": path,
            "state": state_file,
            "director_plan": director_paths["plan"],
            "manifest": delivery_paths["manifest"],
            "delivery_readme": delivery_paths["readme"],
            "audio_plan": audio_path,
        },
        deltas=deltas,
        limits=limits,
    )
    report = root / "production" / "report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(result, workspace), encoding="utf-8")
    result.paths["report"] = report
    return result


def status(workspace: Path, lesson_dir: Path, build_root: Path | None = None) -> dict:
    workspace = workspace.resolve()
    paths = LessonPaths.load(workspace, lesson_dir)
    root = (build_root or paths.build_root).resolve()
    order_file = order_path(root)
    state_file = state_path(root)
    if not order_file.is_file() or not state_file.is_file():
        raise ContractError("no production order/state; run producer-run first")
    order = load_order(order_file)
    state = load_state(state_file)
    manifest_file = root / "producer" / "manifest.json"
    manifest = (
        DeliveryManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
        if manifest_file.is_file()
        else None
    )
    return {
        "order": order,
        "state": state,
        "manifest": manifest,
        "paths": {"order": order_file, "state": state_file, "manifest": manifest_file},
    }


def affected(workspace: Path, lesson_dir: Path, build_root: Path | None = None) -> list[ShotDelta]:
    workspace = workspace.resolve()
    inputs = load_inputs(workspace, lesson_dir)
    root = (build_root or inputs.paths.build_root).resolve()
    plan_file = root / "director" / "director_plan.json"
    state_file = state_path(root)
    if not plan_file.is_file() or not state_file.is_file():
        raise ContractError("run producer-run first: director plan or state missing")
    plan = DirectorPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
    state = load_state(state_file)
    current = build_fingerprints(plan, inputs.paths, root / "director")
    return diff_fingerprints(state.shots if state else [], current)


@dataclass
class RebuildPlan:
    deltas: list[ShotDelta]
    shot_ids: list[str]
    storyboard: Path
    command: list[str]
    authorized: bool
    order: ProductionOrder


def plan_rebuild(
    workspace: Path,
    lesson_dir: Path,
    build_root: Path | None = None,
    compose: bool = False,
) -> RebuildPlan:
    workspace = workspace.resolve()
    inputs = load_inputs(workspace, lesson_dir)
    root = (build_root or inputs.paths.build_root).resolve()
    order_file = order_path(root)
    if not order_file.is_file():
        raise ContractError("run producer-order/producer-run first: order missing")
    order = load_order(order_file)
    storyboard = root / "director" / "storyboard.director.yaml"
    if not storyboard.is_file():
        raise ContractError("director handoff missing; run producer-run first")
    deltas = affected(workspace, lesson_dir, root)
    shot_ids = [delta.shot_id for delta in deltas]
    try:
        relative = storyboard.resolve().relative_to(workspace)
    except ValueError:
        relative = storyboard.resolve()
    command: list[str] = []
    if shot_ids:
        command = [
            "uv",
            "run",
            "--project",
            "CourseControl",
            "course-control",
            "build",
            "--lesson",
            inputs.paths.slug,
            "--storyboard-source",
            "director",
        ]
        for shot_id in shot_ids:
            command += ["--shots", shot_id]
        if not compose:
            command.append("--skip-compose")
    return RebuildPlan(
        deltas=deltas,
        shot_ids=shot_ids,
        storyboard=storyboard,
        command=command,
        authorized=order.authorizations.allow_render,
        order=order,
    )


def _refresh_fingerprints(
    root: Path, paths: LessonPaths, shot_ids: set[str]
) -> ProductionState | None:
    plan_file = root / "director" / "director_plan.json"
    state_file = state_path(root)
    if not plan_file.is_file() or not state_file.is_file():
        return None
    plan = DirectorPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
    state = load_state(state_file)
    if state is None:
        return None
    current = {item.shot_id: item for item in build_fingerprints(plan, paths, root / "director")}
    seen: set[str] = set()
    refreshed = []
    for item in state.shots:
        if item.shot_id in shot_ids and item.shot_id in current:
            refreshed.append(current[item.shot_id])
            seen.add(item.shot_id)
        else:
            refreshed.append(item)
    for shot_id in shot_ids - seen:
        if shot_id in current:
            refreshed.append(current[shot_id])
    state.shots = refreshed
    state.updated_at = now()
    save_state(state, state_file)
    return state


def execute_rebuild(
    rebuild: RebuildPlan,
    workspace: Path,
    lesson_dir: Path,
    build_root: Path | None = None,
    compose: bool = False,
) -> dict:
    if not rebuild.authorized:
        raise ContractError("order.authorizations.allow_render is false; rebuild refused")
    if not rebuild.shot_ids:
        raise ContractError("nothing to rebuild")
    root = (build_root or (workspace / "build" / rebuild.order.lesson_id)).resolve()
    report, report_path = run_build(
        workspace.resolve(),
        lesson_dir.resolve(),
        BuildOptions(
            skip_compose=not compose,
            storyboard=rebuild.storyboard,
            shots=rebuild.shot_ids,
            build_root=root,
        ),
    )
    failed = any(
        stage.name.startswith("render:") and stage.status == Status.FAIL for stage in report.stages
    )
    state = None
    if not failed:
        state = _refresh_fingerprints(root, LessonPaths.load(workspace, lesson_dir), set(rebuild.shot_ids))
    return {"report": report, "report_path": report_path, "failed": failed, "state": state}
