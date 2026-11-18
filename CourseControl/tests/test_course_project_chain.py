"""The course project layer supplies the course contract.

The program repository serves many subjects; the plan, cards, claim index and
forbidden terms belong to ``<content_root>/projects/<course_id>/project.yaml``.
These tests lock that resolution and the fail-closed behaviour.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.production.course_chain import check_lesson_course_chain


class CourseProjectChainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        course = self.root / "runtime" / "course-content" / "demo"
        (course / "episodes" / "T1-01").mkdir(parents=True)
        self.plan = course / "COURSE_MAP.md"
        self.plan.write_text(
            "```yaml curriculum\n"
            "course: demo\n"
            "modules:\n"
            "  - {id: T1, count: 1}\n"
            "```\n\n"
            "| 集 | 集名 | 原书小节 | 页码 | 时长 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| T1-01 | Demo | 1.1 Scope | 22-27 | 12 |\n"
            "demo\n",
            encoding="utf-8",
        )
        (course / "episodes" / "T1-01" / "card.yaml").write_text(
            yaml.safe_dump(
                {
                    "episode": "T1-01",
                    "title": "Demo",
                    "section": "1.1",
                    "concepts": ["1.1"],
                    "figures": [],
                    "target_seconds": 720,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.lesson = self.root / "lessons" / "demo"
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\n"
            "lesson_id: demo\n"
            "course_id: demo\n"
            "episode_id: T1-01\n"
            "duration:\n  target_seconds: 720\n"
            "  min_seconds: 480\n  max_seconds: 900\n",
            encoding="utf-8",
        )
        (self.lesson / "slides.md").write_text("page\n", encoding="utf-8")
        (self.lesson / "lecture_notes.md").write_text("notes\n", encoding="utf-8")
        (self.lesson / "authoring" / "episode.spec.yaml").write_text(
            yaml.safe_dump(
                {
                    "target_seconds": 720,
                    "min_seconds": 480,
                    "max_seconds": 900,
                    "claims": [
                        {"id": "K-DEMO-1", "source": {"chapter": "1", "section": "1.1"}}
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        self.project = self.root / "projects" / "demo" / "project.yaml"
        self.project.parent.mkdir(parents=True)
        self.project.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "project": {
                        "id": "demo",
                        "mode": "course",
                        "title": "Demo",
                        "language": "en",
                        "audience": "test",
                    },
                    "input": {
                        "sources": [
                            {"type": "book", "uri": "docling:demo", "authority": "primary"}
                        ]
                    },
                    "production": {
                        "quality_profile": "standard",
                        "course": {
                            "lesson_count": {"target": 1, "min": 1, "max": 1},
                            "lesson_seconds": {"min": 480, "max": 900},
                            "lesson": "demo",
                            "plan": "runtime/course-content/demo/COURSE_MAP.md",
                            "expected_episode_count": 1,
                            "cards_dir": "runtime/course-content/demo/episodes",
                            "forbidden_slide_terms": ["of 90"],
                        },
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_project_yaml_supplies_the_course_contract(self) -> None:
        result = check_lesson_course_chain(self.root, self.lesson)
        self.assertIsNotNone(result)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.expected_episode_count, 1)
        self.assertEqual(result.discovered_episode_count, 1)

    def test_missing_project_plan_blocks_instead_of_falling_back(self) -> None:
        self.plan.unlink()
        result = check_lesson_course_chain(self.root, self.lesson)
        self.assertIsNotNone(result)
        self.assertFalse(result.ok)
        self.assertTrue(any("no 1-episode plan" in error for error in result.errors), result.errors)


if __name__ == "__main__":
    unittest.main()
