from __future__ import annotations

import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import typer

from course_control.cli.producer import release_approve_command
from course_control.delivery.package import build_package, verify_package
from course_control.release.check import run_release_check
from tests import test_package


class ReleaseChainTest(unittest.TestCase):
    """The real chain on a synthetic course, never the production root."""

    def setUp(self) -> None:
        self.base = test_package.PackageTest("test_package_collects_and_hashes")
        self.base.setUp()
        self.addCleanup(self.base.tearDown)
        self.workspace = self.base.workspace
        self.lesson_dir = self.base.lesson_dir
        self.paths = self.base.paths
        self._env = patch.dict(
            os.environ,
            {
                "COURSEWORKSPACE_MODE": "production",
                "COURSEWORKSPACE_CONTENT_ROOT": str(self.workspace),
            },
            clear=False,
        )
        self._env.start()
        self.addCleanup(self._env.stop)

        (self.lesson_dir / "authoring" / "episode.spec.yaml").write_text(
            "schema_version: 1\n", encoding="utf-8"
        )
        (self.lesson_dir / "authoring" / "quality.rubric.yaml").write_text(
            "schema_version: 1\n", encoding="utf-8"
        )
        timing = self.paths.build_root / "episode" / "timing.json"
        timing.parent.mkdir(parents=True, exist_ok=True)
        timing.write_text("{}", encoding="utf-8")
        meta = (
            self.paths.build_root
            / "narration"
            / "narration.resequenced.meta.json"
        )
        meta.write_text("{}", encoding="utf-8")
        (self.paths.build_root / "quality" / "teaching-qa.json").write_text(
            '{"status": "PASS", "summary": "structural teaching checks"}',
            encoding="utf-8",
        )
        # A synthetic ASR report: the chain is being tested, not speech
        # recognition.  A real release runs the ASR alignment step.
        (self.paths.build_root / "quality" / "asr-alignment.json").write_text(
            '{"status": "PASS", "model": "synthetic", "mean_coverage": 1.0, '
            '"mismatches": [], "uncovered_speech": []}',
            encoding="utf-8",
        )
        # Burned-in subtitles need an ASS band report; use the remotion path so
        # this fixture tests the release chain rather than the burn-in step.
        lesson_yaml = self.lesson_dir / "lesson.yaml"
        lesson_yaml.write_text(
            lesson_yaml.read_text(encoding="utf-8").replace(
                "render: burn_in", "render: remotion"
            ),
            encoding="utf-8",
        )
        from course_control.content.paths import LessonPaths

        self.paths = LessonPaths.load(self.workspace, self.lesson_dir)
        # A film with audio lets media QC measure loudness instead of
        # declaring the release incomplete for a missing stream.
        final = self.paths.build_root / "final" / "course-video.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=white:s=64x64:d=2:r=30",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", str(final),
            ],
            check=True,
            capture_output=True,
        )
        old = time.time() - 3600
        inputs = [
            self.lesson_dir / "lesson.yaml",
            self.lesson_dir / "authoring" / "episode.spec.yaml",
            self.lesson_dir / "authoring" / "quality.rubric.yaml",
            self.lesson_dir / "storyboard.yaml",
            timing,
            meta,
            self.lesson_dir / "subtitles.srt",
            self.lesson_dir / "authoring" / "storyboard-review.json",
            self.lesson_dir / "authoring" / "storyboard-review.html",
            self.lesson_dir / "authoring" / "storyboard-decisions.json",
            self.paths.build_root / "slides" / "slide-001.png",
        ]
        for path in inputs:
            if path.is_file():
                os.utime(path, (old, old))
        os.utime(final, (time.time(), time.time()))

    def _run(self, stage: str, by: str) -> int:
        try:
            release_approve_command(
                lesson="demo",
                project=None,
                lesson_dir=self.workspace / "lessons",
                workspace=self.workspace,
                stage=stage,
                approved_by=by,
                decision="approved",
                note="",
            )
        except typer.Exit as exc:
            return exc.exit_code
        return 0

    def test_review_release_package_verify_on_a_synthetic_course(self) -> None:
        check = run_release_check(self.workspace, paths=self.paths)
        self.assertIn(
            check["status"],
            {"pass", "pass_with_exemption"},
            [(step["id"], step["status"], step["detail"]) for step in check["steps"]],
        )
        self.assertEqual(self._run("review", "alice"), 0)
        self.assertEqual(self._run("release", "bob"), 0)
        manifest, root = build_package(self.paths)
        self.assertEqual(
            manifest["verdict"], "pass", manifest.get("verdict_reasons")
        )
        self.assertEqual(verify_package(root), [])


if __name__ == "__main__":
    unittest.main()
