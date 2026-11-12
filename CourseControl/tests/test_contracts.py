from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

from course_control.content.collect import resolve_annotations
from course_control.content.contracts import (
    AnnotationSpec,
    LegendAnnotationSpec,
    Shot,
    ShotsFile,
    ShotSpec,
    Storyboard,
    TextAnnotationSpec,
    Timeline,
)
from course_control.content.paths import ContractError, LessonPaths, path_problem
from course_control.platform.utils import page_budgets
from course_control.content.validators import validate

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"


class PathRulesTest(unittest.TestCase):
    def test_relative_paths(self):
        self.assertIsNone(path_problem("slides.md"))
        self.assertIsNotNone(path_problem("assets/"))
        self.assertIsNone(path_problem("assets/", allow_dir=True))
        self.assertIsNone(path_problem("assets", allow_dir=True))

    def test_rejects_absolute_and_backslash(self):
        self.assertIsNotNone(path_problem("/abs/path"))
        self.assertIsNotNone(path_problem("C:" + "/abs/path"))
        self.assertIsNotNone(path_problem("a\\b"))
        self.assertIsNotNone(path_problem("../outside"))
        self.assertIsNotNone(path_problem("a//b"))


class ContractTest(unittest.TestCase):
    def test_overlay_requires_presentation(self):
        with self.assertRaises(ValidationError):
            Shot(
                id="shot_001",
                kind="animation",
                source="animation/a.mp4",
                start_s=1,
                duration_s=1,
                timeline_role="overlay",
            )

    def test_base_rejects_presentation(self):
        with self.assertRaises(ValidationError):
            Shot(
                id="slide_001",
                kind="slide",
                source="slides/slide-001.png",
                start_s=0,
                duration_s=1,
                timeline_role="base",
                presentation="cutaway",
            )

    def test_page_budgets(self):
        notes = """
### Slide 1: A
- **时长预算**：90 秒

### Slide 2: B
- **时长预算**：1.5 分钟
"""
        self.assertEqual(page_budgets(notes), [90.0, 90.0])


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lesson_dir = Path(self.temp.name) / "lesson-smoke"
        shutil.copytree(FIXTURE, self.lesson_dir)
        lesson_path = self.lesson_dir / "lesson.yaml"
        data = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
        data["compose"]["mode"] = "deck"
        data["compose"]["base_video"] = None
        data["subtitles"]["enabled"] = False
        data["content"]["subtitles"] = None
        lesson_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_fixture_validates(self):
        paths = LessonPaths.load(WORKSPACE, self.lesson_dir)
        result = validate(paths)
        self.assertTrue(result.ok, [issue.message for issue in result.errors])

    def test_missing_notes_element_fails(self):
        notes = self.lesson_dir / "lecture_notes.md"
        text = notes.read_text(encoding="utf-8").replace("技术核查", "说明")
        notes.write_text(text, encoding="utf-8")
        paths = LessonPaths.load(WORKSPACE, self.lesson_dir)
        result = validate(paths)
        self.assertFalse(result.ok)
        self.assertTrue(any(issue.rule == "V-04" for issue in result.errors))


class AnnotationContractTest(unittest.TestCase):
    def _storyboard(self, **annotation_overrides):
        payload = {
            "id": "ann_001",
            "slide": 2,
            "cue_seconds": 5,
            "duration_s": 10,
            "kind": "text",
            "text": "sin(x) = 0.5",
        }
        payload.update(annotation_overrides)
        return Storyboard(
            schema_version=1,
            lesson="lesson-smoke",
            shots=[
                ShotSpec(
                    id="shot_001",
                    slide=1,
                    engine="blender",
                    scene="scenes/a.blend",
                    cue_seconds=1,
                )
            ],
            annotations=[TextAnnotationSpec(**payload)],
        )

    def test_storyboard_annotations_validate(self):
        storyboard = self._storyboard(position=(0.5, 0.1), align="center")
        self.assertEqual(storyboard.annotations[0].text, "sin(x) = 0.5")
        self.assertEqual(storyboard.annotations[0].position, (0.5, 0.1))

    def test_duplicate_storyboard_ids_rejected(self):
        with self.assertRaises(ValidationError):
            self._storyboard(id="shot_001")

    def test_annotation_position_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            self._storyboard(position=(1.2, 0.1))

    def test_blank_annotation_text_rejected(self):
        with self.assertRaises(ValidationError):
            self._storyboard(text="   ")

    def test_resolve_annotations_offsets_by_page(self):
        storyboard = self._storyboard()
        annotations = resolve_annotations(
            storyboard.annotations,
            page_starts=[0.0, 90.0],
            budgets=[90.0, 90.0],
            total_duration=180.0,
        )
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0].start_s, 95.0)
        self.assertEqual(annotations[0].duration_s, 10.0)

    def test_legend_annotation_validates(self):
        spec = LegendAnnotationSpec(
            id="ann.legend",
            slide=1,
            cue_seconds=0,
            duration_s=5,
            kind="legend",
            colormap="coolwarm",
            min_value=-400,
            max_value=400,
            units="Pa",
        )
        self.assertEqual(spec.bar_height, 240.0)

    def test_legend_range_rejected(self):
        with self.assertRaises(ValidationError):
            LegendAnnotationSpec(
                id="ann.legend",
                slide=1,
                cue_seconds=0,
                duration_s=5,
                kind="legend",
                colormap="coolwarm",
                min_value=400,
                max_value=-400,
                units="Pa",
            )

    def test_resolve_legend_uses_colormap_stops(self):
        spec = LegendAnnotationSpec(
            id="ann.legend",
            slide=1,
            cue_seconds=0,
            duration_s=5,
            kind="legend",
            colormap="coolwarm",
            min_value=-1,
            max_value=1,
            units="Pa",
        )
        annotations = resolve_annotations(
            [spec],
            page_starts=[0.0],
            budgets=[10.0],
            total_duration=10.0,
            colormaps={
                "coolwarm": {
                    "stops": [[0.0, [0.0, 0.0, 1.0]], [1.0, [1.0, 0.0, 0.0]]]
                }
            },
        )
        self.assertEqual(annotations[0].kind, "legend")
        self.assertEqual(annotations[0].stops[1][0], 1.0)
        self.assertEqual(annotations[0].stops[1][1], (1.0, 0.0, 0.0))

    def test_resolve_legend_requires_known_colormap(self):
        spec = LegendAnnotationSpec(
            id="ann.legend",
            slide=1,
            cue_seconds=0,
            duration_s=5,
            kind="legend",
            colormap="missing",
            min_value=-1,
            max_value=1,
            units="Pa",
        )
        with self.assertRaises(ContractError):
            resolve_annotations(
                [spec],
                page_starts=[0.0],
                budgets=[10.0],
                total_duration=10.0,
                colormaps={"coolwarm": {"stops": [[0.0, [0.0, 0.0, 1.0]]]}},
            )

    def test_resolve_annotations_overflow_rejected(self):
        storyboard = self._storyboard(slide=1, cue_seconds=85, duration_s=10)
        with self.assertRaises(ContractError) as raised:
            resolve_annotations(
                storyboard.annotations,
                page_starts=[0.0],
                budgets=[90.0],
                total_duration=90.0,
            )
        self.assertIn("exceeds page", str(raised.exception))


class ShotsFileTest(unittest.TestCase):
    def test_minimal_shots(self):
        data = ShotsFile(
            lesson="lesson-smoke",
            generated_at="2026-11-01T00:00:00+08:00",
            timeline=Timeline(fps=30, resolution=(1920, 1080), total_duration_s=6),
            shots=[
                Shot(
                    id="base",
                    kind="recording",
                    source="slides/recording.mp4",
                    start_s=0,
                    duration_s=6,
                    timeline_role="base",
                )
            ],
        )
        self.assertEqual(data.timeline.total_duration_s, 6)
        self.assertEqual(data.annotations, [])


if __name__ == "__main__":
    unittest.main()
