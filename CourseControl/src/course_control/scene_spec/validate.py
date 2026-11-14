"""Program checks for environment/shot specs.

These checks protect the contract between the AI planner, the Blender builder
and the asset library.  They are not aesthetic gates: a spec that passes still
has to be judged by the rendered frames.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from course_control.platform.workspace_layout import content_root

from .models import EnvironmentSpec, ShotSpec, load_spec

CAMERA_TEMPLATES = {
    "static_hold",
    "dolly_in",
    "dolly_out",
    "pan",
    "tilt",
    "crane",
    "orbit",
    "tracking",
    "parallax",
}
RENDER_PASSES = {"beauty", "ao", "depth", "mist", "normal", "cryptomatte", "emission"}


def _check_grammar(spec: dict, workspace: Path, issues: list[Issue]) -> None:
    value = spec.get("visual_grammar")
    if not value:
        return
    if "@" not in str(value):
        issues.append(Issue("error", f"visual_grammar must be id@version: {value}"))
        return
    grammar_id, version = str(value).rsplit("@", 1)
    registry = workspace / "shared" / "grammars" / "style-presets.json"
    if not registry.is_file():
        issues.append(Issue("error", f"visual grammar registry missing: {registry}"))
        return
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Issue("error", f"visual grammar registry unreadable: {exc}"))
        return
    preset = (data.get("presets") or {}).get(grammar_id)
    if preset is None:
        issues.append(Issue("error", f"visual_grammar preset not found: {grammar_id}"))
        return
    if str(preset.get("version")) != version:
        issues.append(Issue(
            "error",
            f"visual_grammar version mismatch: {grammar_id}@{version} (registry {preset.get('version')})",
        ))


@dataclass(frozen=True)
class Issue:
    level: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "message": self.message}


def _load_library(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(item.get("id")): item for item in data.get("assets", []) if item.get("id")}


def _asset_path(asset: dict, root: Path) -> Path:
    path = Path(str(asset.get("path") or ""))
    return path if path.is_absolute() else root / path


def _check_asset(
    asset_id: str,
    library: dict[str, dict],
    asset_root: Path,
    issues: list[Issue],
    where: str,
) -> None:
    asset = library.get(asset_id)
    if asset is None:
        issues.append(Issue("error", f"{where}: asset not in library: {asset_id}"))
        return
    path = _asset_path(asset, asset_root)
    if not path.exists():
        issues.append(Issue("error", f"{where}: asset file missing: {asset_id} -> {path}"))


def _check_camera(camera, frames: int, fps: int, issues: list[Issue]) -> None:
    template = camera.template
    if template and template not in CAMERA_TEMPLATES:
        issues.append(Issue("error", f"camera: unknown template {template!r}"))
    if template == "orbit":
        if camera.center is None or camera.radius is None:
            issues.append(Issue("error", "camera: orbit needs center and radius"))
    elif template:
        if camera.location is None or camera.end_location is None:
            issues.append(Issue("error", f"camera: {template} needs location and end_location"))
    if camera.keyframes:
        last = max(int(item.get("frame", 1)) for item in camera.keyframes)
        if last > frames:
            issues.append(Issue("warning", f"camera: last keyframe {last} is beyond frames={frames}"))
        for index, item in enumerate(camera.keyframes):
            if not item.get("location") and not item.get("target") and not item.get("lens"):
                issues.append(Issue("warning", f"camera: keyframe {index} changes nothing"))


def _check_render(render, issues: list[Issue]) -> None:
    unknown = sorted(set(render.passes) - RENDER_PASSES)
    if unknown:
        issues.append(Issue("error", f"render: unknown passes: {', '.join(unknown)}"))
    if render.frames > 1 and not render.output.lower().endswith((".mp4", ".mov", ".mkv")):
        issues.append(Issue("warning", f"render: animation output is not a video: {render.output}"))
    if render.frames == 1 and not render.output.lower().endswith((".png", ".jpg", ".exr")):
        issues.append(Issue("warning", f"render: still output is not an image: {render.output}"))


def validate_spec(
    path: Path,
    workspace: Path | None = None,
    library_path: Path | None = None,
) -> list[Issue]:
    path = path.resolve()
    workspace = (workspace or Path.cwd()).resolve()
    root = content_root(workspace)
    asset_root = root / "assets" / "3d"
    library = _load_library(library_path or asset_root / "library.json")
    issues: list[Issue] = []

    try:
        spec = load_spec(path)
    except Exception as exc:  # noqa: BLE001 - surfaced as a validation issue
        return [Issue("error", f"spec: {exc}")]

    if isinstance(spec, ShotSpec):
        env_path = Path(spec.environment)
        if not env_path.is_absolute():
            env_path = path.parent / env_path
        if not env_path.is_file():
            issues.append(Issue("error", f"shot: environment not found: {env_path}"))
            return issues
        try:
            env = load_spec(env_path)
        except Exception as exc:  # noqa: BLE001
            return issues + [Issue("error", f"environment: {exc}")]
        if not isinstance(env, EnvironmentSpec):
            return issues + [Issue("error", f"environment: {env_path} is not an environment spec")]
        if env.asset_root:
            asset_root = Path(env.asset_root)
        fields = {**env.model_dump(), **{
            key: value for key, value in spec.model_dump().items()
            if key in {"objects", "lights", "water"} and value is not None
        }}
        _check_environment(EnvironmentSpec.model_validate(fields), asset_root, library, issues)
        _check_grammar(fields, workspace, issues)
        _check_camera(spec.camera, spec.render.frames, spec.render.fps, issues)
        _check_render(spec.render, issues)
        if spec.duration_s is not None and spec.render.frames > 1:
            actual = spec.render.frames / spec.render.fps
            if abs(actual - spec.duration_s) > 0.25:
                issues.append(Issue(
                    "warning",
                    f"shot: {actual:.2f}s render vs {spec.duration_s:.2f}s declared duration",
                ))
        return issues

    _check_environment(spec, asset_root, library, issues)
    _check_grammar(spec.model_dump(), workspace, issues)
    if spec.camera:
        from .models import CameraSpec

        try:
            camera = CameraSpec.model_validate(spec.camera)
        except Exception as exc:  # noqa: BLE001
            issues.append(Issue("error", f"camera: {exc}"))
        else:
            _check_camera(camera, int(spec.render.get("frames", 1)), int(spec.render.get("fps", 30)), issues)
    return issues


def _check_environment(
    env: EnvironmentSpec,
    asset_root: Path,
    library: dict[str, dict],
    issues: list[Issue],
) -> None:
    _check_asset(env.hdri, library, asset_root, issues, "environment.hdri")
    if env.terrain.material:
        _check_asset(env.terrain.material, library, asset_root, issues, "terrain.material")
    if env.terrain.heightmap:
        if env.terrain.heightmap in library:
            _check_asset(env.terrain.heightmap, library, asset_root, issues, "terrain.heightmap")
        else:
            path = Path(env.terrain.heightmap)
            if not path.is_absolute():
                path = asset_root / path
            if not path.is_file():
                issues.append(Issue("error", f"terrain.heightmap: file missing: {path}"))
    for index, item in enumerate(env.objects):
        asset_id = str(item.get("asset") or "")
        if not asset_id:
            issues.append(Issue("error", f"objects[{index}]: missing asset id"))
            continue
        _check_asset(asset_id, library, asset_root, issues, f"objects[{index}]")
    if env.water:
        size = float(env.water.get("size_m", 6000))
        if size <= 0:
            issues.append(Issue("error", "water.size_m must be positive"))
