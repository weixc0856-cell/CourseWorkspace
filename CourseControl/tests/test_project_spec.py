from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_control.delivery.project import (
    ProjectSpec,
    load_project,
    save_project,
    synthesize_for_lesson,
)
from ._local_lesson import LOCAL, REASON as LOCAL_REASON

WORKSPACE = Path(__file__).resolve().parents[2]


def course_payload() -> dict:
    return {
        "project": {
            "id": "demo-course",
            "mode": "course",
            "title": "Demo course",
            "language": "en",
        },
        "input": {"sources": [{"type": "book", "uri": "book.pdf"}]},
        "production": {"course": {}},
    }


def topic_payload() -> dict:
    return {
        "project": {
            "id": "demo-topic",
            "mode": "topic_video",
            "title": "Demo topic",
            "language": "en",
        },
        "input": {"topic": "How attention works"},
        "production": {"topic_video": {"target_seconds": 600}},
    }


class ProjectSpecTest(unittest.TestCase):
    def test_course_spec_accepts_minimal_input(self) -> None:
        spec = ProjectSpec.model_validate(course_payload())
        self.assertEqual(spec.project.mode, "course")
        self.assertEqual(spec.production.course.lesson_count.target, 40)
        self.assertEqual(spec.execution.autonomy, "A1")
        self.assertFalse(spec.synthesized)

    def test_topic_spec_accepts_minimal_input(self) -> None:
        spec = ProjectSpec.model_validate(topic_payload())
        self.assertEqual(spec.project.mode, "topic_video")
        self.assertIsNone(spec.production.course)
        self.assertEqual(spec.production.topic_video.target_seconds, 600)

    def test_course_without_sources_is_rejected(self) -> None:
        payload = course_payload()
        payload["input"]["sources"] = []
        with self.assertRaises(ValidationError):
            ProjectSpec.model_validate(payload)

    def test_topic_without_topic_is_rejected(self) -> None:
        payload = topic_payload()
        payload["input"]["topic"] = None
        with self.assertRaises(ValidationError):
            ProjectSpec.model_validate(payload)

    def test_topic_mode_without_topic_plan_is_rejected(self) -> None:
        payload = topic_payload()
        payload["production"] = {"course": {}}
        with self.assertRaises(ValidationError):
            ProjectSpec.model_validate(payload)

    def test_lesson_count_range_must_be_ordered(self) -> None:
        payload = course_payload()
        payload["production"]["course"] = {
            "lesson_count": {"target": 10, "min": 30, "max": 50}
        }
        with self.assertRaises(ValidationError):
            ProjectSpec.model_validate(payload)

    def test_project_id_must_be_a_slug(self) -> None:
        payload = course_payload()
        payload["project"]["id"] = "Demo Course"
        with self.assertRaises(ValidationError):
            ProjectSpec.model_validate(payload)

    def test_save_and_load_round_trip(self) -> None:
        spec = ProjectSpec.model_validate(course_payload())
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.yaml"
            save_project(spec, target)
            loaded = load_project(target)
        self.assertEqual(loaded, spec)


class SynthesizedProjectTest(unittest.TestCase):
    @unittest.skipIf(LOCAL is None, LOCAL_REASON)
    def test_existing_lesson_synthesises_a_course_spec(self) -> None:
        spec = synthesize_for_lesson(WORKSPACE, LOCAL.name)
        self.assertTrue(spec.synthesized)
        self.assertEqual(spec.project.id, LOCAL.name)
        self.assertEqual(spec.project.mode, "course")
        self.assertEqual(spec.execution.autonomy, "A0")
        self.assertTrue(spec.input.sources)

    def test_missing_lesson_raises(self) -> None:
        with self.assertRaises(Exception):
            synthesize_for_lesson(WORKSPACE, "no-such-lesson-for-project-test")
