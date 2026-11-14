from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from course_control.review.compare import build_comparison
from course_control.review.shot_review import build_shot_review


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _video(path: Path, *, source: str = "testsrc", duration: float = 2.0) -> Path:
    if source == "black":
        video_source = f"color=c=black:s=320x240:r=30:d={duration}"
    else:
        video_source = f"{source}=duration={duration}:size=320x240:rate=30"
    _ffmpeg(
        "-f", "lavfi", "-i", video_source,
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    )
    return path


def _manifest(video: Path, directory: Path) -> Path:
    log = directory / "build.log"
    log.write_text("spec=a1\noutput=" + str(video) + "\n", encoding="utf-8")
    path = directory / "a1-manifest.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "build_id": "test-build",
        "shot": "a1",
        "status": "pass",
        "output": str(video),
        "render_profile": "blockout",
        "render": {"resolution": [320, 240], "fps": 30, "engine": "BLENDER_EEVEE", "samples": 1},
        "elapsed_s": 1.0,
        "log": str(log),
    }), encoding="utf-8")
    return path


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class ShotReviewTests(unittest.TestCase):
    def test_package_contains_frames_sheet_preview_metadata_and_qc(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            video = _video(tmp / "shot.mp4")
            manifest = _manifest(video, tmp)
            result = build_shot_review(tmp, shot="a1", video=video, manifest=manifest, out_dir=tmp / "review")
            for name in ("first.png", "middle.png", "last.png", "contact-sheet.jpg", "preview.mp4",
                         "metadata.json", "qc.json", "review.md", "logs.txt"):
                self.assertTrue((result.out_dir / name).is_file(), name)
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["shot"], "a1")
            self.assertEqual(metadata["video"]["width"], 320)
            self.assertEqual(metadata["manifest"]["build_id"], "test-build")
            with Image.open(result.out_dir / "contact-sheet.jpg") as sheet:
                self.assertEqual(sheet.size, (960, 540))
            self.assertIn(result.status, {"PASS", "WARN"})

    def test_black_video_fails_qc(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            video = _video(tmp / "black.mp4", source="black", duration=1.0)
            result = build_shot_review(tmp, shot="a1", video=video, out_dir=tmp / "review")
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            black = next(item for item in qc["checks"] if item["id"] == "black")
            self.assertEqual(black["status"], "FAIL")
            self.assertEqual(result.status, "FAIL")

    def test_missing_manifest_is_incomplete_not_pass(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            video = _video(tmp / "shot.mp4")
            result = build_shot_review(tmp, shot="a1", video=video, out_dir=tmp / "review")
            qc = json.loads(result.qc_path.read_text(encoding="utf-8"))
            manifest = next(item for item in qc["checks"] if item["id"] == "manifest")
            self.assertEqual(manifest["status"], "INCOMPLETE")
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["manifest"]["status"], "INCOMPLETE")

    def test_comparison_keeps_takes_side_by_side(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            first = _video(tmp / "v1.mp4")
            second = _video(tmp / "v2.mp4", source="testsrc2")
            target = build_comparison(
                tmp, shot="a1", takes=[("v001", first), ("v002", second)], out=tmp / "compare.jpg"
            )
            self.assertTrue(target.is_file())
            with Image.open(target) as image:
                self.assertEqual(image.width, 640)
                self.assertGreater(image.height, 600)


if __name__ == "__main__":
    unittest.main()
