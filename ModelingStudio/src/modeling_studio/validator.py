from __future__ import annotations

import json
import struct

from PIL import Image, ImageStat

from .config import WorkflowConfig
from .contracts import ModelPlan, ValidationCheck, ValidationReport
from .job import Job, read_json, update_metadata, write_json


def _glb_summary(path) -> tuple[bool, str]:
    try:
        with path.open("rb") as handle:
            header = handle.read(12)
            if len(header) < 12 or header[:4] != b"glTF":
                return False, "bad GLB magic"
            version = struct.unpack("<I", header[4:8])[0]
            if version != 2:
                return False, f"unsupported GLB version {version}"
            chunk_header = handle.read(8)
            if len(chunk_header) < 8:
                return False, "missing JSON chunk"
            length, chunk_type = struct.unpack("<II", chunk_header)
            if chunk_type != 0x4E4F534A:
                return False, "first chunk is not JSON"
            payload = handle.read(length)
            if len(payload) != length:
                return False, "truncated JSON chunk"
            document = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, struct.error) as exc:
        return False, f"cannot read GLB: {exc}"
    meshes = len(document.get("meshes", []))
    nodes = len(document.get("nodes", []))
    if meshes == 0:
        return False, "GLB contains no meshes"
    return True, f"{meshes} meshes, {nodes} nodes"


def _check(checks: list[ValidationCheck], check_id: str, ok: bool, detail: str) -> None:
    checks.append(ValidationCheck(id=check_id, status="pass" if ok else "fail", detail=detail))


def validate_job(config: WorkflowConfig, job: Job) -> ValidationReport:
    plan = ModelPlan.model_validate(read_json(job.model_plan))
    report = read_json(job.scene_dir / "scene_report.json")
    checks: list[ValidationCheck] = []

    blend = job.scene_dir / "model.blend"
    glb = job.scene_dir / "model.glb"
    preview = job.scene_dir / "preview.png"

    _check(
        checks,
        "blend.exists",
        blend.is_file() and blend.stat().st_size > 0,
        f"{blend.name}: {blend.stat().st_size if blend.is_file() else 0} bytes",
    )
    _check(
        checks,
        "glb.exists",
        glb.is_file() and glb.stat().st_size > 1024,
        f"{glb.name}: {glb.stat().st_size if glb.is_file() else 0} bytes",
    )
    if glb.is_file():
        glb_ok, glb_detail = _glb_summary(glb)
        _check(checks, "glb.structure", glb_ok, glb_detail)

    fbx = job.scene_dir / "model.fbx"
    if fbx.is_file():
        _check(checks, "fbx.exists", fbx.stat().st_size > 1024, f"{fbx.name}: {fbx.stat().st_size} bytes")
    else:
        checks.append(ValidationCheck(id="fbx.exists", status="skipped", detail="not produced"))

    if preview.is_file():
        with Image.open(preview) as image:
            image.load()
            width, height = image.size
            expected = tuple(plan.render.resolution)
            _check(
                checks,
                "preview.resolution",
                (width, height) == expected,
                f"{width}x{height} expected {expected[0]}x{expected[1]}",
            )
            mean = ImageStat.Stat(image.convert("L").resize((64, 64))).mean[0]
            _check(checks, "preview.black_frame", mean >= 2.0, f"mean luma {mean:.2f}")
    else:
        _check(checks, "preview.exists", False, f"missing: {preview}")

    issues = report.get("issues", [])
    _check(
        checks,
        "scene.issues",
        not issues,
        "; ".join(issue.get("message", "") for issue in issues[:5]) or "no issues",
    )
    counts = report.get("counts", {})
    _check(checks, "scene.meshes", counts.get("meshes", 0) >= 1, f"{counts.get('meshes', 0)} meshes")
    camera = report.get("scene", {}).get("active_camera")
    _check(checks, "scene.camera", bool(camera), camera or "none")

    object_names = {entry["name"] for entry in report.get("objects", [])}
    missing_parts = [part.id for part in plan.parts if part.id not in object_names]
    _check(
        checks,
        "plan.parts",
        not missing_parts,
        f"missing objects: {missing_parts}" if missing_parts else f"{len(plan.parts)} parts present",
    )

    assigned = sum(
        1
        for entry in report.get("objects", [])
        if entry.get("type") == "MESH" and any(entry.get("materials") or [])
    )
    if plan.materials:
        _check(checks, "scene.materials", assigned >= 1, f"{assigned} meshes with materials")
    else:
        checks.append(ValidationCheck(id="scene.materials", status="skipped", detail="plan has no materials"))

    bounds = report.get("bounds")
    _check(checks, "scene.bounds", bool(bounds), json.dumps(bounds) if bounds else "no bounds")

    status = "fail" if any(check.status == "fail" for check in checks) else "pass"
    files = {
        "blend": str(blend),
        "glb": str(glb),
        "preview": str(preview),
        "scene_report": str(job.scene_dir / "scene_report.json"),
    }
    if fbx.is_file():
        files["fbx"] = str(fbx)
    validation = ValidationReport(
        job_id=job.job_id,
        status=status,
        checks=checks,
        files=files,
        stats={
            "objects": counts.get("objects"),
            "meshes": counts.get("meshes"),
            "materials": counts.get("materials"),
            "plan_parts": len(plan.parts),
        },
    )
    write_json(job.validation, validation)
    update_metadata(job, stage="validate", status=status, checks=len(checks))
    return validation
