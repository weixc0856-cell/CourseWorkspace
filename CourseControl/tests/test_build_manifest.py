from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.scene_spec import manifest_core


def _write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _environment(tmp: Path) -> tuple[Path, Path, Path, Path]:
    content = tmp / "content"
    assets = content / "assets" / "3d"
    _write(assets / "hdri" / "sky.hdr", "hdri")
    _write(assets / "textures" / "rock" / "rock_diffuse.png", "rock")
    _write(assets / "heightmaps" / "h.png", "height")
    _write(assets / "models" / "rock" / "rock.gltf", "gltf")
    _write(assets / "models" / "rock" / "rock.bin", "bin")
    library = {
        "assets": [
            {"id": "hdri.sky", "kind": "hdri", "version": 1, "quality_level": "hero", "path": "hdri/sky.hdr"},
            {"id": "texture.rock", "kind": "texture", "version": 1, "quality_level": "hero", "path": "textures/rock/"},
            {"id": "heightmap.h", "kind": "heightmap", "version": 1, "quality_level": "standard", "path": "heightmaps/h.png"},
            {"id": "model.rock", "kind": "model", "version": 2, "quality_level": "standard", "path": "models/rock/rock.gltf"},
        ]
    }
    library_path = _write(assets / "library.json", json.dumps(library))
    environment = {
        "schema_version": 1,
        "kind": "environment",
        "id": "ridge",
        "asset_root": str(assets),
        "hdri": "hdri.sky",
        "terrain": {"heightmap": "heightmap.h", "material": "texture.rock"},
        "objects": [{"asset": "model.rock"}],
        "camera": {"location": [0, -10, 3], "target": [0, 0, 0]},
        "render": {"engine": "BLENDER_EEVEE", "samples": 16, "resolution": [540, 960], "frames": 1, "fps": 30, "output": "out.png"},
    }
    spec_path = _write(content / "spec.json", json.dumps(environment))
    builder = _write(tmp / "builder.py", "print('builder')\n")
    return spec_path, library_path, builder, content


class BuildManifestTests(unittest.TestCase):
    def test_collect_inputs_includes_assets_and_versions(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            spec_path, library_path, builder, _content = _environment(tmp)
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            inputs = manifest_core.collect_inputs(spec_path, spec, builder, library_path=library_path)
            ids = {item["id"] for item in inputs["assets"]}
            self.assertEqual(ids, {"hdri.sky", "texture.rock", "heightmap.h", "model.rock"})
            model = next(item for item in inputs["assets"] if item["id"] == "model.rock")
            self.assertEqual(model["version"], 2)
            self.assertEqual(model["hash_kind"], "directory")
            self.assertEqual(len(inputs["shot_spec"]["sha256"]), 64)

    def test_cache_key_changes_when_spec_changes(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            spec_path, library_path, builder, _content = _environment(tmp)
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            out = tmp / "out.png"
            render = spec["render"]
            first = manifest_core.cache_key(
                manifest_core.collect_inputs(spec_path, spec, builder, library_path=library_path),
                render, out, "0.2.0", "cinematic_realism",
            )
            spec["camera"]["lens"] = 50
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            second = manifest_core.cache_key(
                manifest_core.collect_inputs(spec_path, spec, builder, library_path=library_path),
                render, out, "0.2.0", "cinematic_realism",
            )
            self.assertNotEqual(first, second)

    def test_prepare_finalize_and_cache_hit(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            spec_path, library_path, builder, _content = _environment(tmp)
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            out = tmp / "out.png"
            manifests = tmp / "manifests"
            prepared = manifest_core.prepare(
                spec_path=spec_path, spec=spec, render=spec["render"], out=out,
                builder_path=builder, library_path=library_path,
                manifest_dir=manifests, use_cache=False, visual_grammar="cinematic_realism",
            )
            self.assertFalse(prepared.cache_hit)
            self.assertEqual(prepared.manifest["status"], "running")
            self.assertTrue(prepared.manifest_path.is_file())
            out.write_bytes(b"rendered")
            manifest_core.finalize(prepared.manifest_path, status="pass", output=out, elapsed_s=1.2)
            passed = json.loads(prepared.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(passed["status"], "pass")
            self.assertEqual(len(passed["cache_key"]), 64)
            self.assertEqual(passed["render"]["resolution"], [540, 960])
            self.assertEqual(passed["render"]["frame_range"], [1, 1])
            self.assertEqual(passed["seed"], 0)

            cached = manifest_core.prepare(
                spec_path=spec_path, spec=spec, render=spec["render"], out=out,
                builder_path=builder, library_path=library_path,
                manifest_dir=manifests, use_cache=True, visual_grammar="cinematic_realism",
            )
            self.assertTrue(cached.cache_hit)
            self.assertEqual(cached.cached_manifest, prepared.manifest_path)

    def test_missing_asset_writes_failed_manifest(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            spec_path, library_path, builder, content = _environment(tmp)
            library = json.loads(library_path.read_text(encoding="utf-8"))
            library["assets"] = [item for item in library["assets"] if item["id"] != "hdri.sky"]
            library_path.write_text(json.dumps(library), encoding="utf-8")
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            manifests = tmp / "manifests"
            with self.assertRaises(manifest_core.ManifestError):
                manifest_core.prepare(
                    spec_path=spec_path, spec=spec, render=spec["render"], out=tmp / "out.png",
                    builder_path=builder, library_path=library_path,
                    manifest_dir=manifests, use_cache=False,
                )
            failed = list(manifests.glob("*.json"))
            self.assertEqual(len(failed), 1)
            data = json.loads(failed[0].read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "fail")
            self.assertIn("hdri.sky", data["error"])


if __name__ == "__main__":
    unittest.main()
