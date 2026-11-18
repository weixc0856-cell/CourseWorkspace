from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from course_control.delivery.package import PackageError, build_package, verify_package
from course_control.content.paths import LessonPaths
from course_control.platform.utils import NO_CONSOLE

LESSON = """schema_version: 1
lesson_id: demo
title_en: Demo
title_zh: 演示
status: draft
content:
  slides: slides.md
  notes: notes.md
  storyboard: storyboard.yaml
  assets: assets/
  subtitles: subtitles.srt
outputs:
  fps: 30
  resolution: [64, 64]
  slides_canvas: [64, 64]
  animation_canvas: [64, 64]
engines: [manim]
compose:
  mode: deck
narration:
  enabled: true
  source: narration.wav
subtitles:
  enabled: true
  render: burn_in
"""

STORYBOARD = """schema_version: 1
lesson: demo
shots:
- id: shot_001
  slide: 1
  engine: manim
  scene: demo.py::DemoScene
  cue_seconds: 0.0
"""


class PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is not available")
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson_dir = self.workspace / "lessons" / "demo"
        (self.lesson_dir / "assets").mkdir(parents=True)
        (self.lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
        (self.lesson_dir / "slides.md").write_text("# Demo\n", encoding="utf-8")
        (self.lesson_dir / "notes.md").write_text("### Slide 1\n", encoding="utf-8")
        (self.lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
        (self.lesson_dir / "subtitles.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n你好\n", encoding="utf-8"
        )
        build = self.workspace / "build" / "demo"
        (build / "final").mkdir(parents=True)
        (build / "quality").mkdir(parents=True)
        (build / "narration").mkdir(parents=True)
        (build / "review").mkdir(parents=True)
        (build / "logs").mkdir(parents=True)
        (build / "narration" / "narration.wav").write_bytes(b"RIFF")
        (build / "narration" / "narration.meta.json").write_text("{}", encoding="utf-8")
        (build / "slides").mkdir()
        Image.new("RGB", (64, 36), (240, 240, 240)).save(
            build / "slides" / "slide-001.png"
        )
        import hashlib

        (build / "slides" / "capture-manifest.json").write_text(
            json.dumps(
                {
                    "lesson": "demo",
                    "slides_sha256": hashlib.sha256(
                        (self.lesson_dir / "slides.md").read_bytes()
                    ).hexdigest(),
                    "total_slides": 1,
                    "captured": 1,
                    "pages": [{"index": 0, "page": "001", "file": "slide-001.png"}],
                }
            ),
            encoding="utf-8",
        )
        (build / "quality" / "media-qc.json").write_text('{"status": "PASS"}', encoding="utf-8")
        quality_report = build / "quality" / "quality-report.json"
        quality_report.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "lesson": "demo",
                    "states": {
                        "VERIFY_PASS": True,
                        "VERIFY_INCOMPLETE": False,
                        "VERIFY_FAIL": False,
                        "BLOCKED_WARNINGS": [],
                        "RELEASE_APPROVED": True,
                    },
                    "dimensions": [
                        {"id": "Q1", "status": "PASS"},
                        {"id": "Q2", "status": "PASS"},
                        {"id": "Q3", "status": "PASS"},
                        {"id": "Q4", "status": "PASS"},
                        {"id": "Q5", "status": "PASS"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        report_sha = hashlib.sha256(quality_report.read_bytes()).hexdigest()
        from course_control.quality.certificate import quality_content_sha256

        quality_content = quality_content_sha256(json.loads(quality_report.read_text("utf-8")))
        (build / "quality" / "certificate.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "project_id": "demo",
                    "generated_at": "now",
                    "verdict": "pass",
                    "quality_report_sha256": report_sha,
                    "quality_report_content_sha256": quality_content,
                }
            ),
            encoding="utf-8",
        )
        for name in ("review-approval.json", "release-approval.json"):
            (build / "quality" / name).write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "lesson": "demo",
                        "decision": "approved",
                        "approved_by": "tester",
                        "quality_report_sha256": report_sha,
                        "quality_report_content_sha256": quality_content,
                    }
                ),
                encoding="utf-8",
            )
        (build / "review" / "review.json").write_text('{"status": "completed"}', encoding="utf-8")
        (build / "logs" / "build.log").write_text("ok\n", encoding="utf-8")
        (build / "final" / "build-report.json").write_text(
            json.dumps({"verdict": "pass", "run_id": "run-1"}), encoding="utf-8"
        )
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=white:s=64x64:d=1:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(build / "final" / "course-video.mp4"),
            ],
            check=True,
            creationflags=NO_CONSOLE,
        )
        report_sha = hashlib.sha256(quality_report.read_bytes()).hexdigest()
        build_report_sha = hashlib.sha256(
            (build / "final" / "build-report.json").read_bytes()
        ).hexdigest()
        final_sha = hashlib.sha256(
            (build / "final" / "course-video.mp4").read_bytes()
        ).hexdigest()
        for name in ("review-approval.json", "release-approval.json"):
            (build / "quality" / name).write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "lesson": "demo",
                        "stage": name.split("-")[0],
                        "decision": "approved",
                        "approved_by": "tester",
                        "build_report_sha256": build_report_sha,
                        "final_video_sha256": final_sha,
                        "quality_report_sha256": report_sha,
                        "quality_report_content_sha256": quality_content,
                    }
                ),
                encoding="utf-8",
            )

        from course_control.authoring.pipeline import sign_storyboard_page
        from course_control.authoring.storyboard_page import build as build_page

        build_page("demo", self.lesson_dir, build, storyboard_path=self.lesson_dir / "storyboard.yaml")
        manifest = json.loads((build / "storyboard" / "manifest.json").read_text("utf-8"))
        (build / "storyboard" / "decisions.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "lesson": "demo",
                    "reviewed_by": "Wei Chen",
                    "storyboard_sha256": manifest.get("storyboard_sha256"),
                    "html_sha256": manifest.get("html_sha256"),
                    "pages": [{**row, "decision": "approve"} for row in manifest["pages_detail"]],
                }
            ),
            encoding="utf-8",
        )
        sign_storyboard_page(self.workspace, self.lesson_dir, "Wei Chen")
        self.paths = LessonPaths.load(self.workspace, self.lesson_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_package_collects_and_hashes(self) -> None:
        manifest, root = build_package(self.paths)
        self.assertEqual(root.resolve(), (self.workspace / "deliver" / "demo").resolve())
        self.assertEqual(manifest["run_id"], "run-1")
        self.assertEqual(manifest["verdict"], "pass")
        paths = {item["path"]: item for item in manifest["files"]}
        self.assertEqual(paths["final/master.mp4"]["status"], "present")
        self.assertEqual(paths["final/subtitles.srt"]["status"], "present")
        self.assertEqual(paths["review/review.json"]["status"], "present")
        self.assertTrue((root / "metadata.json").is_file())
        self.assertTrue((root / "delivery-checklist.md").is_file())
        self.assertEqual(verify_package(root), [])

    def test_verdict_is_incomplete_without_certificate(self) -> None:
        (self.paths.build_root / "quality" / "certificate.json").unlink()
        manifest, _ = build_package(self.paths)
        self.assertEqual(manifest["verdict"], "incomplete")
        self.assertTrue(any("certificate" in reason for reason in manifest["verdict_reasons"]))

    def test_verify_rejects_a_pass_manifest_without_evidence(self) -> None:
        fake = self.workspace / "deliver" / "fake"
        fake.mkdir(parents=True)
        (fake / "manifest.json").write_text(
            json.dumps({"schema_version": 1, "lesson": "demo", "verdict": "pass", "files": []}),
            encoding="utf-8",
        )
        self.assertTrue(verify_package(fake))

    def test_verify_rejects_path_traversal(self) -> None:
        manifest, root = build_package(self.paths)
        payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        payload["files"].append(
            {"path": "../../escape.txt", "required": False, "status": "present", "sha256": "0" * 64}
        )
        (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("unsafe package path" in problem for problem in problems))

    def test_incomplete_attempt_does_not_replace_delivery(self) -> None:
        manifest, root = build_package(self.paths)
        self.assertEqual(manifest["verdict"], "pass")
        (self.paths.build_root / "quality" / "certificate.json").unlink()
        attempt, attempt_root = build_package(self.paths)
        self.assertEqual(attempt["verdict"], "incomplete")
        self.assertFalse(attempt["installed"])
        self.assertTrue(str(attempt_root).endswith(".attempt"))
        installed = json.loads((root / "manifest.json").read_text("utf-8"))
        self.assertEqual(installed["verdict"], "pass")

    def test_missing_master_fails(self) -> None:
        (self.paths.build_root / "final" / "course-video.mp4").unlink()
        with self.assertRaises(PackageError):
            build_package(self.paths)

    def test_failed_rebuild_keeps_the_previous_package(self) -> None:
        manifest, root = build_package(self.paths)
        before = {item["path"]: item.get("sha256") for item in manifest["files"]}
        (self.paths.build_root / "final" / "course-video.mp4").unlink()
        with self.assertRaises(PackageError):
            build_package(self.paths)
        self.assertTrue((root / "manifest.json").is_file())
        self.assertEqual(verify_package(root), [])
        after = {
            item["path"]: item.get("sha256")
            for item in json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )["files"]
        }
        self.assertEqual(before["final/master.mp4"], after["final/master.mp4"])

    def _pass_package(self) -> tuple[dict, Path]:
        manifest, root = build_package(self.paths)
        self.assertEqual(manifest["verdict"], "pass", manifest.get("verdict_reasons"))
        return manifest, root

    def _rewrite_manifest(self, root: Path, mutate) -> dict:
        path = root / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def test_verify_rejects_null_hashes(self) -> None:
        _, root = self._pass_package()

        def null_hashes(payload: dict) -> None:
            for item in payload["files"]:
                item["sha256"] = None

        self._rewrite_manifest(root, null_hashes)
        problems = verify_package(root)
        self.assertTrue(any("no sha256" in item for item in problems), problems)

    def test_verify_rejects_an_approval_for_another_lesson(self) -> None:
        _, root = self._pass_package()
        approval = root / "evidence" / "review-approval.json"
        payload = json.loads(approval.read_text(encoding="utf-8"))
        payload["lesson"] = "other"
        approval.write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("not 'demo'" in item for item in problems), problems)

    def test_verify_rejects_a_wrong_stage_slot(self) -> None:
        _, root = self._pass_package()
        approval = root / "evidence" / "release-approval.json"
        payload = json.loads(approval.read_text(encoding="utf-8"))
        payload["stage"] = "review"
        approval.write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("stage 'review'" in item for item in problems), problems)

    def test_verify_requires_storyboard_evidence(self) -> None:
        _, root = self._pass_package()

        def drop_storyboard(payload: dict) -> None:
            payload["evidence"]["storyboard_required"] = True
            payload["files"] = [
                item
                for item in payload["files"]
                if not str(item.get("path", "")).startswith("evidence/storyboard/")
            ]

        self._rewrite_manifest(root, drop_storyboard)
        problems = verify_package(root)
        self.assertTrue(
            any("evidence/storyboard/review.json" in item for item in problems),
            problems,
        )

    def test_verify_rejects_a_schema_1_approval(self) -> None:
        _, root = self._pass_package()
        approval = root / "evidence" / "review-approval.json"
        payload = json.loads(approval.read_text(encoding="utf-8"))
        payload["schema_version"] = 1
        approval.write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("not 2" in item for item in problems), problems)

    def test_verify_rejects_a_schema_1_quality_report(self) -> None:
        _, root = self._pass_package()
        report = root / "evidence" / "quality-report.json"
        payload = json.loads(report.read_text(encoding="utf-8"))
        payload["schema_version"] = 1
        report.write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("quality report schema_version" in item for item in problems), problems)

    def test_verify_rejects_a_manifest_that_drops_storyboard(self) -> None:
        _, root = self._pass_package()

        def drop(payload: dict) -> None:
            payload["evidence"]["storyboard_required"] = False
            payload["files"] = [
                item for item in payload["files"]
                if not str(item.get("path", "")).startswith("evidence/storyboard/")
            ]

        self._rewrite_manifest(root, drop)
        problems = verify_package(root)
        self.assertTrue(
            any("does not list required: evidence/storyboard/review.json" in item for item in problems)
            or any("disagrees with the quality report" in item for item in problems),
            problems,
        )

    def test_verify_rejects_an_unsigned_storyboard(self) -> None:
        _, root = self._pass_package()
        review = root / "evidence" / "storyboard" / "review.json"
        payload = json.loads(review.read_text(encoding="utf-8"))
        payload["approved_by"] = "human"
        review.write_text(json.dumps(payload), encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("not signed by a named person" in item for item in problems), problems)

    def test_verify_rejects_an_unknown_schema(self) -> None:
        _, root = self._pass_package()
        self._rewrite_manifest(root, lambda payload: payload.update(schema_version=1))
        problems = verify_package(root)
        self.assertTrue(any("not the integer 2" in item for item in problems), problems)

    def test_verify_rejects_a_linked_package_file(self) -> None:
        _, root = self._pass_package()
        outside = self.workspace / "outside.json"
        outside.write_text("x", encoding="utf-8")
        target = root / "metadata.json"
        target.unlink()
        import subprocess

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(outside)],
            capture_output=True,
        )
        if result.returncode != 0:
            self.skipTest("cannot create a junction here")
        problems = verify_package(root)
        self.assertTrue(
            any("linked package file" in item or "unsafe package path" in item for item in problems),
            problems,
        )

    def test_verify_rejects_a_linked_ancestor(self) -> None:
        _, root = self._pass_package()
        outside = self.workspace / "outside-dir"
        outside.mkdir()
        (outside / "payload").write_text("x", encoding="utf-8")
        link = root / "evidence" / "linked"
        import subprocess

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
        )
        if result.returncode != 0:
            self.skipTest("cannot create a junction here")

        def add_linked(payload: dict) -> None:
            payload["files"].append(
                {"path": "evidence/linked/payload", "required": True, "status": "present", "sha256": "0" * 64}
            )

        self._rewrite_manifest(root, add_linked)
        problems = verify_package(root)
        self.assertTrue(any("unsafe package path" in item for item in problems), problems)

    def test_package_root_junction_is_refused(self) -> None:
        outside = self.workspace / "outside-deliver"
        outside.mkdir()
        target = self.workspace / "deliver" / "demo"
        target.parent.mkdir(parents=True)
        import subprocess

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(outside)],
            capture_output=True,
        )
        if result.returncode != 0:
            self.skipTest("cannot create a junction here")
        with self.assertRaises(PackageError):
            build_package(self.paths)

    def test_manifest_paths_are_relative(self) -> None:
        manifest, _ = self._pass_package()
        for item in manifest["files"]:
            value = str(item.get("path") or "")
            self.assertFalse(value.startswith("/") or (len(value) > 1 and value[1] == ":"), value)

    def test_fail_verdict_does_not_replace_a_passing_delivery(self) -> None:
        _, root = self._pass_package()
        certificate = self.paths.build_root / "quality" / "certificate.json"
        payload = json.loads(certificate.read_text(encoding="utf-8"))
        payload["verdict"] = "fail"
        certificate.write_text(json.dumps(payload), encoding="utf-8")
        attempt, attempt_root = build_package(self.paths)
        self.assertEqual(attempt["verdict"], "fail")
        self.assertFalse(attempt["installed"])
        self.assertTrue(str(attempt_root).endswith(".attempt"))
        installed = json.loads((root / "manifest.json").read_text("utf-8"))
        self.assertEqual(installed["verdict"], "pass")

    def test_tampered_package_is_detected(self) -> None:
        manifest, root = build_package(self.paths)
        target = root / "metadata.json"
        target.write_text("{}", encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("hash mismatch" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
