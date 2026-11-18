from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from course_control.delivery.media_package import verify_media_package
from course_control.platform.utils import probe_media, which_command
from course_control.quality.speech_alignment import THRESHOLDS


class CleanMediaPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.master = Path(cls.shared.name) / "master.mp4"
        subprocess.run(
            [
                *which_command("ffmpeg"), "-v", "error",
                "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", "-y", str(cls.master),
            ],
            check=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "ws"
        self.workspace.mkdir()
        self.probe = probe_media(self.master).as_dict()

    def tearDown(self):
        self.tmp.cleanup()

    def _sha(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _record(self, path: Path) -> dict:
        return {
            "path": path.relative_to(self.root).as_posix(),
            "required": True,
            "status": "present",
            "bytes": path.stat().st_size,
            "sha256": self._sha(path),
        }

    def build(self) -> dict:
        master = self.root / "final" / "master.mp4"
        master.parent.mkdir(parents=True)
        shutil.copy2(self.master, master)
        stem = self.root / "narration" / "stem.wav"
        stem.parent.mkdir(parents=True)
        shutil.copy2(self.master, stem)
        script = self.root / "evidence" / "script.source.json"
        script.parent.mkdir(parents=True)
        script.write_text(
            json.dumps({"captions": [{"index": 1, "start_s": 0.0, "end_s": 1.0, "en": "Hello"}]}),
            encoding="utf-8",
        )
        timed = self.root / "evidence" / "script.timed.json"
        timed.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
        provenance = self.root / "evidence" / "narration.provenance.json"
        provenance.write_text(
            json.dumps(
                {
                    "sample_id": "sample",
                    "script_sha256": self._sha(script),
            "timed_script_sha256": self._sha(timed),
                    "stem": {"path": str(stem), "sha256": self._sha(stem), "duration_s": 1.0},
                }
            ),
            encoding="utf-8",
        )
        asr = self.root / "evidence" / "asr-alignment.json"
        asr.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "bad_segments": [],
                    "uncovered_speech_s": 0,
                    "thresholds": THRESHOLDS,
                    "master_sha256": self._sha(master),
                    "script_sha256": self._sha(timed),
                }
            ),
            encoding="utf-8",
        )
        coverage = self.root / "evidence" / "subtitle-coverage.json"
        coverage.write_text(json.dumps({"cues": 1, "covered_s": 1.0}), encoding="utf-8")
        srt = self.root / "final" / "subtitles.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        metadata = self.root / "metadata.json"
        metadata.write_text(
            json.dumps(
                {
                    "id": "sample",
                    "publication": False,
                    "duration_s": self.probe["duration"],
                    "resolution": [self.probe["width"], self.probe["height"]],
                }
            ),
            encoding="utf-8",
        )
        checklist = self.root / "delivery-checklist.md"
        checklist.write_text("# checklist" + chr(10), encoding="utf-8")
        files = [
            self._record(path)
            for path in (master, srt, script, timed, provenance, asr, coverage, stem, metadata, checklist)
        ]
        checks = [
            {"id": step, "status": "pass", "detail": ""}
            for step in (
                "final_video", "media_probe", "expected", "decode",
                "black", "freeze", "subtitles", "evidence",
                "narration", "asr", "loudness",
            )
        ]
        manifest = {
            "schema_version": 3,
            "kind": "media_sample",
            "id": "sample",
            "scope": "internal_sample",
            "publication": False,
            "verdict": "pass",
            "narration_kind": "clean_tts",
            "script_sha256": self._sha(script),
            "timed_script_sha256": self._sha(timed),
            "stem": {"path": "narration/stem.wav", "sha256": self._sha(stem), "duration_s": 1.0},
            "expected": {
                "min_s": 0.5, "max_s": 2,
                "width": self.probe["width"], "height": self.probe["height"],
                "fps": self.probe["fps"], "audio": True,
            },
            "probe": self.probe,
            "subtitle_coverage": {
                "cues": 1, "covered_s": 1.0, "last_end_s": 1.0,
                "coverage_ratio": 1.0,
            },
            "subtitle_policy": {"min_coverage_ratio": 0.9, "must_reach_end": True},
            "evidence_count": 3,
            "checks": checks,
            "files": files,
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def verify(self, asr_result: dict | None = None) -> list[str]:
        fresh = asr_result or {
            "status": "PASS",
            "bad_segments": [],
            "uncovered_speech_s": 0,
            "thresholds": THRESHOLDS,
        }
        with patch("course_control.quality.speech_alignment.run_alignment", return_value=fresh):
            return verify_media_package(self.root, self.workspace)

    def test_clean_package_with_passing_fresh_asr_passes(self):
        self.build()
        self.assertEqual(self.verify(), [])

    def test_saved_pass_but_fresh_asr_fails(self):
        self.build()
        problems = self.verify({"status": "FAIL", "bad_segments": [1], "uncovered_speech_s": 0.5, "thresholds": THRESHOLDS})
        self.assertTrue(any("independent ASR failed" in item for item in problems))

    def test_missing_asr_is_incomplete(self):
        self.build()
        problems = self.verify({"status": "INCOMPLETE", "errors": ["model missing"], "thresholds": THRESHOLDS})
        self.assertTrue(any(item.startswith("INCOMPLETE:") for item in problems))

    def test_provenance_script_hash_mismatch_fails(self):
        manifest = self.build()
        provenance_path = self.root / "evidence" / "narration.provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["script_sha256"] = "0" * 64
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        for item in manifest["files"]:
            if item["path"] == "evidence/narration.provenance.json":
                item["sha256"] = self._sha(provenance_path)
                item["bytes"] = provenance_path.stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = self.verify()
        self.assertTrue(any("provenance script_sha256" in item for item in problems))

    def test_stem_hash_mismatch_fails(self):
        manifest = self.build()
        stem = self.root / "narration" / "stem.wav"
        stem.write_bytes(b"changed")
        for item in manifest["files"]:
            if item["path"] == "narration/stem.wav":
                item["sha256"] = self._sha(stem)
                item["bytes"] = stem.stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = self.verify()
        self.assertTrue(any("stem sha256" in item for item in problems))

    def test_missing_saved_asr_is_incomplete(self):
        self.build()
        (self.root / "evidence" / "asr-alignment.json").unlink()
        problems = self.verify()
        self.assertTrue(any(item.startswith("INCOMPLETE:") for item in problems))

    def test_saved_asr_master_hash_is_checked(self):
        manifest = self.build()
        asr = self.root / "evidence" / "asr-alignment.json"
        data = json.loads(asr.read_text(encoding="utf-8"))
        data["master_sha256"] = "0" * 64
        asr.write_text(json.dumps(data), encoding="utf-8")
        for item in manifest["files"]:
            if item["path"] == "evidence/asr-alignment.json":
                item["sha256"] = self._sha(asr)
                item["bytes"] = asr.stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = self.verify()
        self.assertTrue(any("master_sha256" in item for item in problems))

    def test_clean_manifest_requires_narration_asr_loudness(self):
        manifest = self.build()
        manifest["checks"] = [
            item for item in manifest["checks"]
            if item["id"] not in {"narration", "asr", "loudness"}
        ]
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = self.verify()
        for step in ("narration", "asr", "loudness"):
            self.assertTrue(any(f"check '{step}' is missing" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
