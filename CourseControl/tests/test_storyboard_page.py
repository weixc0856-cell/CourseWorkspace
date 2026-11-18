from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from course_control.authoring.pipeline import (
    assert_storyboard_signed,
    sign_storyboard_page,
)
from course_control.production.course_chain import check_lesson_course_chain
from PIL import Image

from course_control.authoring.storyboard_page import build, split_slides
from course_control.cli.authoring import storyboard_review_command

PLAN_TEXT = """```yaml curriculum
course: demo-course
modules:
  - {id: T1, count: 80}
```

| 集 | 集名 | 原书小节 | 页码 | 时长 |
| --- | --- | --- | --- | --- |
| T1-01 | Demo Lesson | 1.1 Scope | 22-27 | 12 |
demo
"""



class StoryboardPageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lesson = self.root / "lessons" / "demo"
        self.lesson.mkdir(parents=True)
        (self.lesson / "assets").mkdir()
        (self.lesson / "lecture_notes.md").write_text("notes\n", encoding="utf-8")
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ntitle_en: Demo Lesson\n"
            "title_zh: Demo\nstatus: draft\n"
            "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
            "  storyboard: storyboard.yaml\n  assets: assets/\n"
            "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
            "  slides_canvas: [1280, 720]\n  animation_canvas: [1920, 1080]\n"
            "engines: [manim]\ncompose:\n  mode: deck\n",
            encoding="utf-8",
        )
        (self.lesson / "slides.md").write_text(
            "<style>.x{color:red}</style>\n<h1>Opening</h1>\n---\n<h2>Second page</h2>\n",
            encoding="utf-8",
        )
        self.storyboard = self.lesson / "storyboard.yaml"
        self.storyboard.write_text(
            "schema_version: 1\nlesson: demo\nshots:\n"
            "  - id: s1\n    slide: 1\n    engine: manim\n"
            "    scene: demo/scene.py::Demo\n    cue_seconds: 0\n"
            "    expected_duration_s: 8\n    note: Air is a speed tax\n",
            encoding="utf-8",
        )
        self.build_root = self.root / "build" / "demo"
        (self.build_root / "slides").mkdir(parents=True)
        Image.new("RGB", (64, 36), (240, 240, 240)).save(
            self.build_root / "slides" / "slide-001.png"
        )
        Image.new("RGB", (64, 36), (240, 240, 240)).save(
            self.build_root / "slides" / "slide-002.png"
        )
        self._write_capture_manifest()

    def _write_capture_manifest(self, slides_sha: str | None = None) -> None:
        import hashlib

        digest = slides_sha or hashlib.sha256(
            (self.lesson / "slides.md").read_bytes()
        ).hexdigest()
        (self.build_root / "slides" / "capture-manifest.json").write_text(
            json.dumps(
                {
                    "lesson": "demo",
                    "slides_sha256": digest,
                    "total_slides": 2,
                    "captured": 2,
                    "pages": [
                        {"index": 0, "page": "001", "file": "slide-001.png"},
                        {"index": 1, "page": "002", "file": "slide-002.png"},
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _approve_all(self, rejected: set[int] | None = None) -> None:
        rejected = rejected or set()
        manifest = json.loads((self.build_root / "storyboard" / "manifest.json").read_text("utf-8"))
        rows = [
            {**row, "decision": "reject" if int(row["page"]) in rejected else "approve"}
            for row in manifest["pages_detail"]
        ]
        (self.build_root / "storyboard" / "decisions.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "lesson": "demo",
                    "reviewed_by": "Wei Chen",
                    "storyboard_sha256": manifest.get("storyboard_sha256"),
                    "html_sha256": manifest.get("html_sha256"),
                    "course_chain_fingerprint": manifest.get("course_chain_fingerprint"),
                    "pages": rows,
                }
            ),
            encoding="utf-8",
        )

    def _bind_course(self) -> Path:
        lesson_path = self.lesson / "lesson.yaml"
        lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
        lesson["course_id"] = "demo-course"
        lesson["episode_id"] = "T1-01"
        lesson["duration"] = {
            "target_seconds": 720,
            "min_seconds": 480,
            "max_seconds": 900,
        }
        lesson_path.write_text(
            yaml.safe_dump(lesson, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        course_root = self.root / "runtime" / "course-content" / "demo-course"
        card = course_root / "episodes" / "T1-01" / "card.yaml"
        card.parent.mkdir(parents=True)
        card.write_text(
            yaml.safe_dump(
                {
                    "episode": "T1-01",
                    "title": "Demo Lesson",
                    "section": "1.1",
                    "core_question": "Demo Lesson",
                    "concepts": ["1.1"],
                    "figures": [],
                    "target_seconds": 720,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        plan = course_root / "COURSE_MAP.md"
        plan.write_text(PLAN_TEXT, encoding="utf-8")
        (self.lesson / "authoring").mkdir(exist_ok=True)
        (self.lesson / "authoring" / "episode.spec.yaml").write_text(
            yaml.safe_dump(
                {
                    "target_seconds": 720,
                    "min_seconds": 480,
                    "max_seconds": 900,
                    "claims": [
                        {"id": "C01", "source": {"chapter": "1", "section": "1.1"}}
                    ],
                }
            ),
            encoding="utf-8",
        )

        config = self.root / "course-chain.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 2,
                    "courses": {
                        "demo-course": {
                            "expected_episode_count": 80,
                            "plan": "runtime/course-content/demo-course/COURSE_MAP.md",
                            "cards_dir": "runtime/course-content/demo-course/episodes",
                            "lessons_root": "lessons",
                            "forbidden_lesson_slugs": {},
                            "forbidden_slide_terms": [],
                        }
                    },
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return config

    def test_split_slides_ignores_style_and_separators(self):
        self.assertEqual(split_slides((self.lesson / "slides.md").read_text("utf-8")), ["Opening", "Second page"])

    def test_page_contains_every_slide_and_names_missing_captures(self):
        manifest = build("demo", self.lesson, self.build_root)
        self.assertEqual(manifest["pages"], 2)
        self.assertEqual(manifest["shots"], 1)
        self.assertEqual(manifest["missing_captures"], [])
        html = (self.build_root / "storyboard" / "index.html").read_text("utf-8")
        self.assertIn("Opening", html)
        self.assertIn("Second page", html)
        self.assertIn("Air is a speed tax", html)
        self.assertIn("data:image/png;base64", html)

    def test_signoff_then_storyboard_change_blocks(self):
        build("demo", self.lesson, self.build_root)
        self._approve_all()
        sign_storyboard_page(self.root, self.lesson, "Wei Chen")
        assert_storyboard_signed(self.lesson, self.storyboard)
        review = json.loads((self.lesson / "authoring" / "storyboard-review.json").read_text("utf-8"))
        self.assertEqual(review["pages"], 2)
        self.storyboard.write_text(self.storyboard.read_text("utf-8") + "  - id: s2\n    slide: 2\n", encoding="utf-8")
        with self.assertRaises(Exception):
            assert_storyboard_signed(self.lesson, self.storyboard)

    def test_reviewed_page_change_blocks(self):
        build("demo", self.lesson, self.build_root)
        self._approve_all()
        sign_storyboard_page(self.root, self.lesson, "Wei Chen")
        reviewed = self.lesson / "authoring" / "storyboard-review.html"
        reviewed.write_text(reviewed.read_text(encoding="utf-8") + "<!-- edit -->", encoding="utf-8")
        with self.assertRaises(Exception):
            assert_storyboard_signed(self.lesson, self.storyboard)

    def test_missing_reviewed_page_blocks(self):
        build("demo", self.lesson, self.build_root)
        self._approve_all()
        sign_storyboard_page(self.root, self.lesson, "Wei Chen")
        (self.lesson / "authoring" / "storyboard-review.html").unlink()
        with self.assertRaises(Exception):
            assert_storyboard_signed(self.lesson, self.storyboard)

    def test_missing_capture_blocks_signoff(self):
        (self.build_root / "slides" / "slide-002.png").unlink()
        build("demo", self.lesson, self.build_root)
        self._approve_all()
        with self.assertRaises(Exception):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_zero_byte_capture_is_missing(self):
        (self.build_root / "slides" / "slide-002.png").write_bytes(b"")
        manifest = build("demo", self.lesson, self.build_root)
        self.assertEqual(manifest["missing_captures"], [2])

    def test_zero_page_storyboard_is_rejected(self):
        (self.lesson / "slides.md").write_text("", encoding="utf-8")
        (self.lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\nshots: []\n", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            build("demo", self.lesson, self.build_root)

    def test_rebuilt_page_voids_old_decisions(self):
        build("demo", self.lesson, self.build_root)
        storyboard_review_command(
            lesson="demo", approve="1,2", reject="", by="Wei Chen",
            lesson_dir=self.lesson, workspace=self.root
        )
        (self.lesson / "slides.md").write_text(
            "<h1>Opening changed</h1>\n---\n<h2>Second page changed</h2>\n", encoding="utf-8"
        )
        self._write_capture_manifest()
        build("demo", self.lesson, self.build_root)
        storyboard_review_command(
            lesson="demo", approve="", reject="", by="Wei Chen",
            lesson_dir=self.lesson, workspace=self.root
        )
        decisions = json.loads(
            (self.build_root / "storyboard" / "decisions.json").read_text("utf-8")
        )
        self.assertTrue(all(row["decision"] == "pending" for row in decisions["pages"]))

    def test_rejected_page_blocks_signoff(self):
        build("demo", self.lesson, self.build_root)
        self._approve_all(rejected={2})
        with self.assertRaises(Exception):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_unsigned_gate_blocks(self):
        build("demo", self.lesson, self.build_root)
        with self.assertRaises(Exception):
            assert_storyboard_signed(self.lesson, self.storyboard)

    def test_changed_slides_with_old_captures_is_rejected(self):
        build("demo", self.lesson, self.build_root)
        (self.lesson / "slides.md").write_text(
            "<h1>Opening v2</h1>\n---\n<h2>Second page v2</h2>\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "different slides.md"):
            build("demo", self.lesson, self.build_root)

    def test_unbound_captures_block_signoff(self):
        (self.build_root / "slides" / "capture-manifest.json").write_text(
            json.dumps(
                {
                    "lesson": "demo",
                    "total_slides": 2,
                    "captured": 2,
                    "pages": [
                        {"index": 0, "page": "001", "file": "slide-001.png"},
                        {"index": 1, "page": "002", "file": "slide-002.png"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        build("demo", self.lesson, self.build_root)
        self._approve_all()
        with self.assertRaisesRegex(Exception, "no source hash"):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_stale_page_is_rejected(self):
        build("demo", self.lesson, self.build_root)
        self.storyboard.write_text(self.storyboard.read_text("utf-8") + "\n# changed\n", encoding="utf-8")
        with self.assertRaises(Exception):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_course_chain_change_voids_signoff(self):
        config = self._bind_course()
        with mock.patch.dict(
            os.environ, {"COURSEWORKSPACE_CHAIN_CONFIG": str(config)}
        ):
            chain = check_lesson_course_chain(
                self.root, self.lesson, config_path=config
            )
            self.assertIsNotNone(chain)
            self.assertTrue(chain.ok, chain.errors)
            manifest = build(
                "demo",
                self.lesson,
                self.build_root,
                course_chain={
                    "course_id": chain.course_id,
                    "episode_id": chain.episode_id,
                    "fingerprint": chain.fingerprint,
                },
            )
            self.assertEqual(
                manifest["course_chain_fingerprint"], chain.fingerprint
            )
            self._approve_all()
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")
            assert_storyboard_signed(self.lesson, self.storyboard)

            spec = self.lesson / "authoring" / "episode.spec.yaml"
            spec.write_text(
                yaml.safe_dump({"claims": [], "note": "changed"}),
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                assert_storyboard_signed(self.lesson, self.storyboard)


if __name__ == "__main__":
    unittest.main()
