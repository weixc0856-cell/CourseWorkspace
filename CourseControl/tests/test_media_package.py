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


def write_package(root: Path, *, publication: bool = False, verdict: str = "pass") -> None:
    master = root / "final" / "master.mp4"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"fake video bytes")
    manifest = {
        "schema_version": 3,
        "kind": "media_sample",
        "id": "sample",
        "publication": publication,
        "verdict": verdict,
        "files": [
            {
                "path": "final/master.mp4",
                "required": True,
                "status": "present",
                "bytes": master.stat().st_size,
                "sha256": __import__("hashlib").sha256(master.read_bytes()).hexdigest(),
            }
        ],
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
