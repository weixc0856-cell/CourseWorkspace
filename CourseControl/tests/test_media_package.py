from __future__ import annotations

import json
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


def write_package(root: Path, *, publication: bool = False, verdict: str = "pass", scope: str = "internal_sample") -> None:
    master = root / "final" / "master.mp4"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"fake video bytes")
    metadata = root / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "id": "sample",
                "publication": False,
                "duration_s": 1.0,
                "resolution": [640, 360],
            }
        ),
        encoding="utf-8",
    )
    checklist = root / "delivery-checklist.md"
    checklist.write_text("# checklist" + chr(10), encoding="utf-8")
    files = []
    for path in (master, metadata, checklist):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "required": True,
                "status": "present",
                "bytes": path.stat().st_size,
                "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            }
        )
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
        "expected": {"min_s": 0.5, "max_s": 2, "width": 640, "height": 360, "fps": 30, "audio": True},
        "probe": {"duration": 1.0, "width": 640, "height": 360, "fps": 30, "has_audio": True},
        "subtitle_coverage": None,
        "evidence_count": 0,
        "checks": checks,
        "files": files,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class MediaPackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_package_verifies(self):
        write_package(self.root)
        self.assertEqual(verify_media_package(self.root), [])

    def test_tampered_file_is_reported(self):
        write_package(self.root)
        (self.root / "final" / "master.mp4").write_bytes(b"changed")
        problems = verify_media_package(self.root)
        self.assertTrue(any("sha256 mismatch" in item for item in problems))

    def test_missing_file_is_reported(self):
        write_package(self.root)
        (self.root / "final" / "master.mp4").unlink()
        problems = verify_media_package(self.root)
        self.assertTrue(any("missing required file" in item for item in problems))

    def test_publication_true_is_rejected(self):
        write_package(self.root, publication=True)
        problems = verify_media_package(self.root)
        self.assertTrue(any("publication: false" in item for item in problems))

    def test_failed_verdict_is_rejected(self):
        write_package(self.root, verdict="fail")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not pass" in item for item in problems))

    def test_schema_two_is_rejected(self):
        write_package(self.root)
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        manifest["schema_version"] = 2
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("schema_version" in item for item in problems))

    def test_trimmed_manifest_cannot_hide_missing_files(self):
        write_package(self.root)
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"] = [item for item in manifest["files"] if item["path"] == "final/master.mp4"]
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for path in ("metadata.json", "delivery-checklist.md"):
            (self.root / path).unlink()
        problems = verify_media_package(self.root)
        self.assertTrue(any("does not record required file" in item for item in problems))

    def test_extra_file_is_reported(self):
        write_package(self.root)
        (self.root / "extra.txt").write_text("x", encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not in the manifest" in item for item in problems))

    def test_failed_check_is_reported(self):
        write_package(self.root)
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        manifest["checks"][0]["status"] = "fail"
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("not pass" in item for item in problems))

    def test_wrong_scope_is_rejected(self):
        write_package(self.root, scope="public")
        problems = verify_media_package(self.root)
        self.assertTrue(any("scope" in item for item in problems))

    def test_metadata_mismatch_is_reported(self):
        write_package(self.root)
        metadata = json.loads((self.root / "metadata.json").read_text(encoding="utf-8"))
        metadata["duration_s"] = 99
        (self.root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            if item["path"] == "metadata.json":
                item["sha256"] = __import__("hashlib").sha256((self.root / "metadata.json").read_bytes()).hexdigest()
                item["bytes"] = (self.root / "metadata.json").stat().st_size
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_media_package(self.root)
        self.assertTrue(any("metadata duration" in item for item in problems))

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
