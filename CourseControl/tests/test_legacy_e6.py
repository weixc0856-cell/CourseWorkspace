from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from course_control.legacy_e6 import (
    LegacyE6Error,
    LegacyShot,
    adapt_e6_manifest,
    asset_ref,
    build_shot_timings,
    load_manifest,
    parse_rate,
    parse_srt,
    seconds_to_ms,
    sha256_file,
)

WORKSPACE = Path(__file__).resolve().parents[2]
E6 = WORKSPACE / "build" / "manim-transformer" / "e6"
E6_FILES = [
    E6 / "manifest.json",
    E6 / "narration.wav",
    E6 / "subtitles.srt",
    E6 / "transformer_attention_final.mp4",
    E6 / "media" / "videos" / "transformer_explainer" / "1080p30" / "TokensScene.mp4",
    E6 / "media" / "videos" / "transformer_explainer" / "1080p30" / "QKVScene.mp4",
    E6 / "media" / "videos" / "transformer_explainer" / "1080p30" / "AttentionScene.mp4",
    E6 / "media" / "videos" / "transformer_explainer" / "1080p30" / "OutputScene.mp4",
]


def legacy_manifest(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "lesson": "e6-test",
        "resolution": [1920, 1080],
        "fps": 30,
        "shots": [
            {
                "id": "s1",
                "scene": "SceneOne",
                "file": "a.mp4",
                "duration_s": 1.0,
                "sha256": "a" * 64,
            }
        ],
        "narration": {
            "file": "n.wav",
            "duration_s": 1.0,
            "sha256": "b" * 64,
            "segments": [{"id": "e6-s1", "duration_s": 1.0}],
        },
        "subtitles": {"file": "s.srt", "sha256": "c" * 64},
        "video": {"file": "v.mp4", "duration_s": 1.0, "sha256": "d" * 64},
        "checks": {"scenes": "pass"},
    }
    payload.update(overrides)
    return payload


class SecondsTest(unittest.TestCase):
    def test_seconds_to_ms(self):
        self.assertEqual(seconds_to_ms(8.0), 8000)
        self.assertEqual(seconds_to_ms(7.533), 7533)
        self.assertEqual(seconds_to_ms(9.667), 9667)
        self.assertEqual(seconds_to_ms(7.9), 7900)
        self.assertEqual(seconds_to_ms(33.1), 33100)

    def test_invalid_seconds_rejected(self):
        for value in (-1, "8.0", True):
            with self.subTest(value=value), self.assertRaises(LegacyE6Error):
                seconds_to_ms(value)


class LegacyManifestTest(unittest.TestCase):
    def _write(self, payload: dict) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            json.dump(payload, handle)
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_valid_manifest_loads(self):
        manifest = load_manifest(self._write(legacy_manifest()))
        self.assertEqual(manifest.lesson, "e6-test")
        self.assertEqual(manifest.shots[0].duration_s, 1.0)

    def test_schema_version_must_be_one(self):
        with self.assertRaises(LegacyE6Error):
            load_manifest(self._write(legacy_manifest(schema_version=2)))

    def test_bad_hash_rejected(self):
        payload = legacy_manifest()
        payload["shots"][0]["sha256"] = "not-a-hash"
        with self.assertRaises(LegacyE6Error):
            load_manifest(self._write(payload))


class ShotTimingTest(unittest.TestCase):
    def test_cumulative_frames_match_e6(self):
        shots = [
            LegacyShot(id="s1", scene="A", file="a.mp4", duration_s=8.0, sha256="a" * 64),
            LegacyShot(id="s2", scene="B", file="b.mp4", duration_s=7.533, sha256="b" * 64),
            LegacyShot(id="s3", scene="C", file="c.mp4", duration_s=9.667, sha256="c" * 64),
            LegacyShot(id="s4", scene="D", file="d.mp4", duration_s=7.9, sha256="d" * 64),
        ]
        timings, total = build_shot_timings(shots, 30, 1)
        self.assertEqual(
            [(item.start_frame, item.duration_frames) for item in timings],
            [(0, 240), (240, 226), (466, 290), (756, 237)],
        )
        self.assertEqual(total, 993)


class SrtAndRateTest(unittest.TestCase):
    def test_parse_srt(self):
        cues = parse_srt(
            "1\n00:00:00,500 --> 00:00:07,300\nfirst\n\n"
            "2\n00:00:08,500 --> 00:00:14,000\nsecond\n"
        )
        self.assertEqual(len(cues), 2)
        self.assertEqual((cues[0].start_ms, cues[0].end_ms), (500, 7300))
        self.assertEqual(cues[1].text, "second")

    def test_bad_srt_rejected(self):
        with self.assertRaises(LegacyE6Error):
            parse_srt("1\n00:00:01,000 --> 00:00:01,000\nempty")
        with self.assertRaises(LegacyE6Error):
            parse_srt("")

    def test_parse_rate(self):
        self.assertEqual(parse_rate("30000/1001"), (30000, 1001))
        self.assertIsNone(parse_rate("0/0"))
        self.assertIsNone(parse_rate(None))
        self.assertIsNone(parse_rate("bad"))


class AssetRefTest(unittest.TestCase):
    def test_asset_ref_uses_relative_path_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "sub" / "a.bin"
            path.parent.mkdir()
            path.write_bytes(b"abc")
            ref = asset_ref(path, root, "data")
            self.assertEqual(ref.path, "sub/a.bin")
            self.assertEqual(ref.sha256, hashlib.sha256(b"abc").hexdigest())
            self.assertEqual(ref.bytes, 3)
            self.assertEqual(ref.origin, "rendered")

    def test_missing_asset_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(LegacyE6Error):
                asset_ref(Path(temp) / "missing", Path(temp), "data")


@unittest.skipUnless(all(path.is_file() for path in E6_FILES), "E6 V0 build artifacts not present")
class E6IntegrationTest(unittest.TestCase):
    def test_adapter_reads_v0_without_modifying_it(self):
        before = sha256_file(E6 / "manifest.json")
        render, checks = adapt_e6_manifest(
            E6 / "manifest.json",
            workspace=WORKSPACE,
            run_id="20261107T120000Z-deadbeef",
            now=datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc),
        )
        after = sha256_file(E6 / "manifest.json")

        self.assertEqual(before, after)
        self.assertIsNone(render.source)
        self.assertEqual(render.output.total_frames, 993)
        self.assertEqual(render.output.duration_ms, 33100)
        self.assertEqual(
            [(shot.shot_id, shot.start_frame, shot.duration_frames) for shot in render.shots],
            [("s1", 0, 240), ("s2", 240, 226), ("s3", 466, 290), ("s4", 756, 237)],
        )
        self.assertFalse([check for check in checks if check.status == "fail"])
        manual = [check for check in checks if check.id == "manual_checks_not_trusted"]
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual[0].status, "not_applicable")
        self.assertFalse(render.legacy["manual_checks_trusted"])
        self.assertEqual(render.legacy["manual_checks"]["scenes"], "pass")
        self.assertEqual(render.run_id, "20261107T120000Z-deadbeef")


if __name__ == "__main__":
    unittest.main()
