from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from pydantic import ValidationError

from course_control.platform import workspace_layout
from course_control.scene_spec import load_spec, validate_spec
from course_control.scene_spec.models import EnvironmentSpec, ShotSpec


def _environment(**overrides):
    data = {
        "kind": "environment",
        "id": "t.ridge",
        "hdri": "hdri.sky",
        "terrain": {"material": "texture.rock", "heightmap": "heightmap.h"},
        "render": {"frames": 1},
    }
    data.update(overrides)
    return data


def _shot(**overrides):
    data = {
        "kind": "shot",
        "id": "a1",
        "environment": "environments/ridge.json",
        "camera": {
            "template": "dolly_in",
            "location": [0, -10, 3],
            "end_location": [0, -8, 3],
            "target": [0, 0, 0],
        },
        "render": {"frames": 30, "output": "a1.mp4"},
    }
    data.update(overrides)
    return data


class SceneSpecTests(unittest.TestCase):
    def test_environment_keeps_unknown_fields_out(self):
        with self.assertRaises(ValidationError):
            EnvironmentSpec.model_validate(_environment(typo_field=1))

    def test_shot_requires_a_camera(self):
        with self.assertRaises(ValidationError):
            ShotSpec.model_validate(_shot(camera={}))

    def test_dolly_template_needs_an_end(self):
        with self.assertRaises(ValidationError):
            ShotSpec.model_validate(_shot(camera={
                "template": "dolly_in", "location": [0, -10, 3], "target": [0, 0, 0]
            }))

    def test_tilt_uses_end_target_with_a_fixed_camera(self):
        parsed = ShotSpec.model_validate(_shot(camera={
            "template": "tilt",
            "location": [0, -10, 3],
            "target": [0, 0, 0],
            "end_target": [0, 0, 6],
        }))
        self.assertEqual(parsed.camera.template, "tilt")

    def test_orbit_needs_center_and_radius(self):
        with self.assertRaises(ValidationError):
            ShotSpec.model_validate(_shot(camera={"template": "orbit", "target": [0, 0, 0]}))

    def test_load_spec_reads_an_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "env.json"
            path.write_text(json.dumps(_environment()), encoding="utf-8")
            parsed = load_spec(path)
            self.assertIsInstance(parsed, EnvironmentSpec)
            self.assertEqual(parsed.id, "t.ridge")

    def test_validate_reports_missing_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            (content / "assets" / "3d").mkdir(parents=True)
            (content / "assets" / "3d" / "library.json").write_text(
                json.dumps({"assets": [{"id": "hdri.sky", "path": "hdri/sky.hdr"}]}),
                encoding="utf-8",
            )
            spec_dir = content / "assets" / "3d" / "kits" / "t" / "environments"
            spec_dir.mkdir(parents=True)
            spec = spec_dir / "ridge.json"
            spec.write_text(json.dumps(_environment()), encoding="utf-8")
            with mock.patch.dict(os.environ, {workspace_layout.ENV_VAR: str(content)}):
                workspace_layout.reset_cache()
                issues = validate_spec(spec, content)
            workspace_layout.reset_cache()
            messages = "\n".join(item.message for item in issues)
            self.assertIn("terrain.material: asset not in library", messages)
            self.assertIn("asset file missing: hdri.sky", messages)

    def test_visual_grammar_yaml_and_json_are_in_sync(self):
        root = Path(__file__).resolve().parents[2]
        yaml_data = yaml.safe_load((root / "shared" / "grammars" / "style-presets.yaml").read_text(encoding="utf-8"))
        json_data = json.loads((root / "shared" / "grammars" / "style-presets.json").read_text(encoding="utf-8"))
        self.assertEqual(set(yaml_data["presets"]), set(json_data["presets"]))
        for key in yaml_data["presets"]:
            self.assertEqual(
                str(yaml_data["presets"][key].get("version")),
                str(json_data["presets"][key].get("version")),
            )
            self.assertEqual(
                yaml_data["presets"][key].get("builder"),
                json_data["presets"][key].get("builder"),
            )

    def test_visual_grammar_version_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            (content / "assets" / "3d").mkdir(parents=True)
            (content / "assets" / "3d" / "library.json").write_text(
                json.dumps({"assets": [
                    {"id": "hdri.sky", "path": "hdri/sky.hdr"},
                    {"id": "texture.rock", "path": "textures/rock/"},
                    {"id": "heightmap.h", "path": "heightmaps/h.png"},
                ]}), encoding="utf-8"
            )
            for path in ("hdri/sky.hdr", "textures/rock/diffuse.png", "heightmaps/h.png"):
                target = content / "assets" / "3d" / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            grammar = Path(__file__).resolve().parents[2] / "shared" / "grammars" / "style-presets.json"
            (content / "shared" / "grammars").mkdir(parents=True)
            (content / "shared" / "grammars" / "style-presets.json").write_text(
                grammar.read_text(encoding="utf-8"), encoding="utf-8"
            )
            spec_dir = content / "assets" / "3d" / "kits" / "t" / "environments"
            spec_dir.mkdir(parents=True)
            spec = spec_dir / "ridge.json"
            spec.write_text(json.dumps(_environment(
                visual_grammar="cinematic_realism@1.0",
                asset_root=str(content / "assets" / "3d"),
            )), encoding="utf-8")
            with mock.patch.dict(os.environ, {workspace_layout.ENV_VAR: str(content)}):
                workspace_layout.reset_cache()
                issues = validate_spec(spec, content)
            workspace_layout.reset_cache()
            messages = chr(10).join(item.message for item in issues)
            self.assertNotIn("visual_grammar", messages)

            data = json.loads(spec.read_text(encoding="utf-8"))
            data["visual_grammar"] = "cinematic_realism@9.9"
            spec.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.dict(os.environ, {workspace_layout.ENV_VAR: str(content)}):
                workspace_layout.reset_cache()
                issues = validate_spec(spec, content)
            workspace_layout.reset_cache()
            self.assertTrue(any("version mismatch" in item.message for item in issues))

    def test_capabilities_mirror_the_validator(self):
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root / "shared" / "scene-specs" / "capabilities.json").read_text(encoding="utf-8"))
        from course_control.scene_spec.validate import CAMERA_TEMPLATES, RENDER_PASSES

        self.assertEqual(set(data["camera_templates"]), CAMERA_TEMPLATES)
        self.assertEqual(set(data["render_passes"]), RENDER_PASSES)


if __name__ == "__main__":
    unittest.main()
