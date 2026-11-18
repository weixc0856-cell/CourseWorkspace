from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from course_control.delivery.media_package import (
    MediaPackageError,
    MediaSampleSpec,
    _srt_coverage,
    load_media_spec,
    verify_media_package,
)
from course_control.platform.utils import probe_media, which_command


class MediaPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.master = Path(cls.shared.name) / "master.mp4"
        command = [
            *which_command("ffmpeg"),
            "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", "-y", str(cls.master),
        ]
        subprocess.run(command, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.probe = probe_media(self.master).as_dict()

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, path: Path) -> dict:
        return {
            "path": path.relative_to(self.root).as_posix(),
            "required": True,
            "status": "present",
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def write_package(
        self,
        *,
        publication: bool = False,
        verdict: str = "pass",
        scope: str = "internal_sample",
        subtitles: bool = False,
        subtitle_policy: dict | None = None,
        coverage_override: dict | None = None,
    ) -> dict:
        master = self.root / "final" / "master.mp4"
        master.parent.mkdir(parents=True)
        shutil.copy2(self.master, master)
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
        files = [self._record(path) for path in (master, metadata, checklist)]
        coverage = None
        policy = None
        if subtitles:
            srt = self.root / "final" / "subtitles.srt"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:00,800\nOne line\n",
                encoding="utf-8",
            )
            files.append(self._record(srt))
            coverage = _srt_coverage(srt)
            coverage = {
                **coverage,
                "coverage_ratio": round(coverage["covered_s"] / self.probe["duration"], 4),
            }
            policy = subtitle_policy or {"min_coverage_ratio": 0.7, "must_reach_end": False}
        if coverage_override is not None and coverage is not None:
            coverage = {**coverage, **coverage_override}
        checks = [
            {"id": step, "status": "pass", "detail": ""}
            for step in (
                "final_video", "media_probe", "expected", "decode",
                "black", "freeze", "subtitles", "evidence",
            )
        ]
        manifest = {
            "schema_version": 3,
            "kind": "media_sample",
            "id": "sample",
            "scope": scope,
            "publication": publication,
            "verdict": verdict,
            "expected": {
                "min_s": 0.5,
                "max_s": 2,
                "width": self.probe["width"],
                "height": self.probe["height"],
                "fps": self.probe["fps"],
                "audio": True,
            },
            "probe": self.probe,
            "subtitle_coverage": coverage,
            "subtitle_policy": policy,
            "evidence_count": 0,
            "checks": checks,
            "files": files,
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_valid_package_verifies(self):
        self.write_package()
        self.assertEqual(verify_media_package(self.root), [])

    def test_fake_master_with_self_consistent_manifest_fails(self):
        manifest = self.write_package()
        fake = self.root / "final" / "master.mp4"
        fake.write_bytes(b"fake")
        for item in manifest["files"]:
            if item["path"] == "final/master.mp4":
                item["bytes"] = fake.stat().st_size
                item["sha256"] = hashlib.sha256(fake.read_bytes()).hexdigest()
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not readable" in item for item in problems), problems)

    def test_tampered_file_is_reported(self):
        self.write_package()
        (self.root / "final" / "master.mp4").write_bytes(b"changed")
        problems = verify_media_package(self.root)
        self.assertTrue(any("sha256 mismatch" in item for item in problems))

    def test_missing_file_is_reported(self):
        self.write_package()
        (self.root / "final" / "master.mp4").unlink()
        problems = verify_media_package(self.root)
        self.assertTrue(any("missing required file" in item for item in problems))

    def test_publication_true_is_rejected(self):
        self.write_package(publication=True)
        problems = verify_media_package(self.root)
        self.assertTrue(any("publication: false" in item for item in problems))

    def test_failed_verdict_is_rejected(self):
        self.write_package(verdict="fail")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not pass" in item for item in problems))

    def test_schema_two_is_rejected(self):
        manifest = self.write_package()
        manifest["schema_version"] = 2
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("schema_version" in item for item in problems))

    def test_trimmed_manifest_cannot_hide_missing_files(self):
        manifest = self.write_package()
        manifest["files"] = [item for item in manifest["files"] if item["path"] == "final/master.mp4"]
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for path in ("metadata.json", "delivery-checklist.md"):
            (self.root / path).unlink()
        problems = verify_media_package(self.root)
        self.assertTrue(any("does not record required file" in item for item in problems))

    def test_extra_file_is_reported(self):
        self.write_package()
        (self.root / "extra.txt").write_text("x", encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not in the manifest" in item for item in problems))

    def test_failed_check_is_reported(self):
        manifest = self.write_package()
        manifest["checks"][0]["status"] = "fail"
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not pass" in item for item in problems))

    def test_wrong_scope_is_rejected(self):
        self.write_package(scope="public")
        problems = verify_media_package(self.root)
        self.assertTrue(any("scope" in item for item in problems))

    def test_metadata_mismatch_is_reported(self):
        manifest = self.write_package()
        metadata = json.loads((self.root / "metadata.json").read_text(encoding="utf-8"))
        metadata["duration_s"] = 99
        (self.root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        for item in manifest["files"]:
            if item["path"] == "metadata.json":
                item["sha256"] = hashlib.sha256((self.root / "metadata.json").read_bytes()).hexdigest()
                item["bytes"] = (self.root / "metadata.json").stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("metadata duration" in item for item in problems))

    def test_forged_subtitle_coverage_fails(self):
        self.write_package(subtitles=True, coverage_override={"covered_s": 1.0, "coverage_ratio": 1.0})
        problems = verify_media_package(self.root)
        self.assertTrue(any("subtitle covered_s does not match" in item for item in problems))

    def test_subtitle_policy_failure_is_reported(self):
        self.write_package(
            subtitles=True,
            subtitle_policy={"min_coverage_ratio": 0.9, "must_reach_end": False},
        )
        problems = verify_media_package(self.root)
        self.assertTrue(any("below policy" in item for item in problems))

    def test_srt_coverage_merges_overlaps(self):
        path = self.root / "a.srt"
        path.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nA\n\n"
            "2\n00:00:01,000 --> 00:00:03,000\nB\n\n"
            "3\n00:00:10,000 --> 00:00:12,000\nC\n",
            encoding="utf-8",
        )
        info = _srt_coverage(path)
        self.assertEqual(info["cues"], 3)
        self.assertEqual(info["covered_s"], 5.0)

    def test_spec_window_must_be_ordered(self):
        with self.assertRaises(ValueError):
            MediaSampleSpec.model_validate(
                {
                    "schema_version": 1,
                    "id": "sample",
                    "title": "Sample",
                    "video": "x.mp4",
                    "expected": {
                        "min_s": 10,
                        "max_s": 5,
                        "width": 1920,
                        "height": 1080,
                        "fps": 30,
                    },
                }
            )

    def test_missing_spec_is_reported(self):
        with self.assertRaises(MediaPackageError):
            load_media_spec(self.root / "missing.yaml")


if __name__ == "__main__":
    unittest.main()
