"""Assemble the seven-part delivery package and its manifest."""
from __future__ import annotations

import json
from pathlib import Path

from ..director.planners import resolve_scene
from ..director.schema import DirectorPlan
from ..paths import LessonPaths
from .order import now
from .schema import (
    ArtifactRecord,
    DeliveryItem,
    DeliveryManifest,
    ProductionOrder,
)
from .state import sha256_file


def _rel(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _artifact(path: Path, workspace: Path, required: bool = True) -> ArtifactRecord:
    exists = path.is_file()
    return ArtifactRecord(
        path=_rel(path, workspace),
        sha256=sha256_file(path) if exists else None,
        bytes=path.stat().st_size if exists else None,
        required=required,
        status="present" if exists else "missing",
    )


def _planned(label: str) -> ArtifactRecord:
    return ArtifactRecord(path=label, required=True, status="missing")


def _item(item_id: str, title: str, files: list[ArtifactRecord], note: str = "") -> DeliveryItem:
    required = [item for item in files if item.required]
    present = sum(1 for item in required if item.status == "present")
    if present == len(required):
        status = "present"
    elif present == 0:
        status = "blocked"
    else:
        status = "partial"
    return DeliveryItem(id=item_id, title=title, status=status, files=files, note=note)


def _script_files(paths: LessonPaths, workspace: Path) -> list[ArtifactRecord]:
    auth = paths.lesson.authoring
    files: list[ArtifactRecord] = []
    for name in ("brief", "outline", "script"):
        relative = getattr(auth, name, None)
        if relative:
            files.append(_artifact(paths.lesson_dir / relative, workspace, required=True))
    if auth.sources:
        files.append(_artifact(paths.lesson_dir / auth.sources, workspace, required=False))
    files.append(_artifact(paths.lesson_dir / paths.lesson.content.slides, workspace, required=False))
    files.append(_artifact(paths.lesson_dir / paths.lesson.content.notes, workspace, required=False))
    return files


def _storyboard_files(build_root: Path, workspace: Path) -> list[ArtifactRecord]:
    director = build_root / "director"
    files = [
        _artifact(director / "director_plan.json", workspace),
        _artifact(director / "storyboard.director.yaml", workspace),
    ]
    directions = director / "directions"
    if directions.is_dir():
        for path in sorted(directions.glob("*.json")):
            files.append(_artifact(path, workspace))
    else:
        files.append(_planned("(missing) directions/"))
    return files


def _asset_files(plan: DirectorPlan, paths: LessonPaths, build_root: Path, workspace: Path) -> list[ArtifactRecord]:
    files: list[ArtifactRecord] = []
    for shot in plan.shots:
        if shot.engine == "remotion":
            continue
        source = resolve_scene(paths, shot.engine, shot.scene)
        if source is None or not source.is_file():
            files.append(_planned(f"(planned) {shot.id} {shot.engine}"))
            continue
        files.append(_artifact(source, workspace, required=True))
    animation = build_root / "animation"
    if animation.is_dir():
        for path in sorted(animation.glob("*.mp4")):
            files.append(_artifact(path, workspace, required=False))
    return files


def _audio_files(paths: LessonPaths, build_root: Path, workspace: Path) -> list[ArtifactRecord]:
    files = [
        _artifact(build_root / "narration" / "narration.wav", workspace),
        _artifact(build_root / "narration" / "narration.meta.json", workspace, required=False),
        _artifact(
            build_root / "audio" / "audio_plan.json",
            workspace,
            required=bool(paths.lesson.audio.bgm),
        ),
    ]
    if paths.lesson.content.subtitles:
        files.append(_artifact(paths.lesson_dir / paths.lesson.content.subtitles, workspace))
    elif paths.lesson.subtitles.enabled and paths.lesson.subtitles.mode == "word":
        files.append(_artifact(build_root / "subtitles.words.json", workspace))
    return files


def _config_files(paths: LessonPaths, build_root: Path, workspace: Path) -> list[ArtifactRecord]:
    files = [
        _artifact(paths.lesson_dir / "lesson.yaml", workspace),
        _artifact(build_root / "production" / "order.json", workspace),
        _artifact(build_root / "production" / "toolchain.json", workspace),
        _artifact(build_root / "production" / "state.json", workspace, required=False),
    ]
    return files


def _acceptance_files(paths: LessonPaths, build_root: Path, workspace: Path) -> list[ArtifactRecord]:
    report = build_root / "final" / "build-report.json"
    files = [
        _artifact(report, workspace),
        _artifact(build_root / "director" / "director_review.md", workspace),
        _artifact(build_root / "production" / "report.md", workspace, required=False),
    ]
    if report.is_file():
        try:
            verdict = json.loads(report.read_text(encoding="utf-8")).get("verdict", "unknown")
        except (OSError, json.JSONDecodeError):
            verdict = "unreadable"
        if verdict != "pass":
            files.append(_planned(f"(build-report verdict: {verdict})"))
    return files


def build_manifest(
    order: ProductionOrder,
    plan: DirectorPlan,
    paths: LessonPaths,
    build_root: Path,
    workspace: Path,
) -> DeliveryManifest:
    final_files = [
        _artifact(build_root / "final" / "course-video.mp4", workspace),
        _artifact(build_root / "final" / "course-video-captioned.mp4", workspace, required=False),
    ]
    if paths.lesson.branding.enabled:
        final_files.append(
            _artifact(build_root / "final" / "course-video-delivery.mp4", workspace)
        )
    items = [
        _item("01_final_video", "最终成片", final_files),
        _item("02_script", "剧本与讲稿", _script_files(paths, workspace)),
        _item("03_storyboard", "导演分镜", _storyboard_files(build_root, workspace)),
        _item("04_assets", "原始素材", _asset_files(plan, paths, build_root, workspace)),
        _item("05_audio", "声音资产", _audio_files(paths, build_root, workspace)),
        _item("06_config", "项目配置", _config_files(paths, build_root, workspace)),
        _item("07_acceptance", "验收报告", _acceptance_files(paths, build_root, workspace)),
    ]
    missing = [
        f"{item.id}: {record.path}"
        for item in items
        for record in item.files
        if record.required and record.status != "present"
    ]
    if any(item.status != "present" for item in items):
        status = "blocked"
    elif order.approved_by:
        status = "delivered"
    else:
        status = "awaiting_approval"
    return DeliveryManifest(
        lesson_id=plan.lesson_id,
        order_id=order.order_id,
        generated_at=now(),
        status=status,
        items=items,
        missing=missing,
    )


def _readme(order: ProductionOrder, manifest: DeliveryManifest) -> str:
    lines = [
        f"# Delivery — {order.lesson_id}",
        "",
        f"- order: `{order.order_id}`",
        f"- status: **{manifest.status}**",
        f"- approved by: {order.approved_by or 'pending'}",
        f"- generated: {manifest.generated_at}",
        "",
        "## Items",
        "",
        "| item | status | files present | note |",
        "| --- | --- | ---: | --- |",
    ]
    for item in manifest.items:
        present = sum(1 for record in item.files if record.status == "present")
        lines.append(f"| {item.id} {item.title} | {item.status} | {present}/{len(item.files)} | {item.note} |")
    lines += ["", "## Missing", ""]
    lines += [f"- {entry}" for entry in manifest.missing] or ["- none"]
    lines += [
        "",
        "## Policy",
        "",
        "- `skip` is never reported as `pass`; a missing required file keeps the item blocked.",
        "- `delivered` requires every item present and a human-approved order.",
        "- Paths are workspace-relative; media is referenced, not duplicated.",
        "",
    ]
    return "\n".join(lines)


def write_manifest(manifest: DeliveryManifest, order: ProductionOrder, build_root: Path) -> dict[str, Path]:
    out = build_root / "delivery"
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readme = out / "README.md"
    readme.write_text(_readme(order, manifest), encoding="utf-8")
    return {"manifest": manifest_path, "readme": readme}
