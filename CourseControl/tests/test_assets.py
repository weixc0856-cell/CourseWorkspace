from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.assets import collect_external_assets, describe_asset, safe_bundle_name


class AssetAddressingTest(unittest.TestCase):
    def test_configured_roots_give_stable_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            (workspace / "config").mkdir()
            bgm = Path(tmp) / "library"
            bgm.mkdir()
            track = bgm / "theme.wav"
            track.write_bytes(b"RIFF")
            (workspace / "config" / "local-paths.yaml").write_text(
                f"bgm_root: {bgm.as_posix()}\n", encoding="utf-8"
            )
            asset = describe_asset(workspace, track, license_status="public_domain")
            self.assertEqual(asset["asset_id"], "bgm:theme.wav")
            self.assertEqual(asset["origin"], "bgm")
            self.assertTrue(asset["sha256"])
            self.assertEqual(asset["license_status"], "public_domain")

    def test_workspace_asset_is_not_external(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "config").mkdir()
            track = workspace / "lessons" / "demo" / "assets" / "a.wav"
            track.parent.mkdir(parents=True)
            track.write_bytes(b"RIFF")
            asset = describe_asset(workspace, track)
            self.assertEqual(asset["origin"], "workspace")
            self.assertEqual(asset["asset_id"], "workspace:lessons/demo/assets/a.wav")

    def test_collect_reads_mix_and_narration_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            build = workspace / "build" / "demo"
            (workspace / "config").mkdir(parents=True)
            (build / "audio").mkdir(parents=True)
            (build / "narration").mkdir(parents=True)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            track = outside / "theme.wav"
            voice = outside / "voice.wav"
            track.write_bytes(b"RIFF")
            voice.write_bytes(b"RIFF")
            (build / "audio" / "mix.json").write_text(
                json.dumps({"source_asset": describe_asset(workspace, track)}),
                encoding="utf-8",
            )
            (build / "narration" / "narration.meta.json").write_text(
                json.dumps({"segments": [{"voice_ref": str(voice)}, {"voice_ref": str(voice)}]}),
                encoding="utf-8",
            )
            assets = collect_external_assets(workspace, build)
            self.assertEqual(len(assets), 2)
            self.assertTrue(all(item["origin"] in {"external", "voice-ref"} for item in assets))

    def test_bundle_names_are_safe_and_unique(self) -> None:
        first = safe_bundle_name({"path": "D:/a b/声音.wav"})
        second = safe_bundle_name({"path": "D:/other/声音.wav"})
        self.assertNotEqual(first, second)
        self.assertNotIn(" ", first)
        self.assertTrue(first.endswith(".wav"))


if __name__ == "__main__":
    unittest.main()
