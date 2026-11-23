"""V-49 mode declaration consistency + duration profile override recording (E3)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from course_control.content.duration import PROFILES, resolve
from course_control.content.paths import LessonPaths
from course_control.content.validators import validate
from course_control.content.contracts import LessonConfig

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-authoring"

SHOTS_HEADER = "# DERIVED from authoring/production.yaml (shots-mode authority). Do not edit by hand.\n"
DECK_HEADER = "# DERIVED from authoring/production.yaml (deck-mode authority). Do not edit by hand.\n"


class ModeDeclarationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lesson = self.root / "lessons" / "lesson-authoring"
        shutil.copytree(FIXTURE, self.lesson)
        scene = self.root / "ManimSandbox" / "lesson-authoring" / "scene.py"
        scene.parent.mkdir(parents=True)
        scene.write_text(
            "from manim import Scene\n\n\nclass AuthoringScene(Scene):\n    pass\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _validate(self):
        return validate(LessonPaths.load(self.root, self.lesson))

    def _prepend_header(self, header: str):
        storyboard = self.lesson / "storyboard.yaml"
        storyboard.write_text(
            header + storyboard.read_text(encoding="utf-8"), encoding="utf-8"
        )

    def _v49(self, result):
        return [issue for issue in result.issues if issue.rule == "V-49"]

    def test_deck_lesson_with_shots_header_fails(self):
        # Negative case: the T1-01 incident — compose.mode switched to deck
        # but the derived storyboard still claims shots-mode authority.
        self._prepend_header(SHOTS_HEADER)
        problems = self._v49(self._validate())
        self.assertTrue(problems)
        self.assertEqual(problems[0].level, "error")
        self.assertIn("shots-mode", problems[0].message)
        self.assertIn("deck", problems[0].message)

    def test_matching_header_passes(self):
        self._prepend_header(DECK_HEADER)
        self.assertFalse(self._v49(self._validate()))

    def test_no_declaration_passes(self):
        self.assertFalse(self._v49(self._validate()))

    def test_shots_mode_lesson_with_deck_header_fails(self):
        import yaml

        lesson_yaml = self.lesson / "lesson.yaml"
        text = lesson_yaml.read_text(encoding="utf-8").replace("mode: deck", "mode: shots")
        text += "\nproduction: authoring/production.yaml\n"
        lesson_yaml.write_text(text, encoding="utf-8")
        production = {
            "schema_version": 1,
            "lesson": "lesson-authoring",
            "sequences": [
                {
                    "id": "seq-01",
                    "title": "one shot",
                    "shots": [
                        {
                            "id": "shot-001",
                            "duration_s": 6.0,
                            "purpose": "compare",
                            "visual_type": "diagram_animated",
                            "grammar": "simulation",
                            "renderer": "motion_canvas",
                            "source": "MotionStudio/src/scenes/demo.ts",
                        }
                    ],
                }
            ],
        }
        (self.lesson / "authoring").mkdir(parents=True, exist_ok=True)
        (self.lesson / "authoring" / "production.yaml").write_text(
            yaml.safe_dump(production, allow_unicode=True), encoding="utf-8"
        )
        self._prepend_header(DECK_HEADER)
        problems = self._v49(self._validate())
        self.assertTrue(problems)
        self.assertIn("deck-mode", problems[0].message)


class DurationOverrideTest(unittest.TestCase):
    def _lesson(self, duration_yaml: str) -> LessonConfig:
        import yaml

        text = (FIXTURE / "lesson.yaml").read_text(encoding="utf-8")
        start = text.index("duration:")
        end = text.index("acceptance:")
        merged = text[:start] + duration_yaml + "\n" + text[end:]
        return LessonConfig.model_validate(yaml.safe_load(merged))

    def test_explicit_values_recorded_as_overrides(self):
        lesson = self._lesson(
            "duration:\n  profile: news\n  target_seconds: 6\n  min_seconds: 5\n  max_seconds: 7\n"
        )
        policy = resolve(lesson)
        self.assertIsNotNone(policy)
        overrides = policy.profile_overrides()
        defaults = PROFILES["news"]
        self.assertEqual(
            overrides,
            {
                "target_seconds": {"profile": defaults["target"], "declared": 6.0},
                "min_seconds": {"profile": defaults["min"], "declared": 5.0},
                "max_seconds": {"profile": defaults["max"], "declared": 7.0},
            },
        )
        # Behavior unchanged: explicit values stay the authority.
        self.assertEqual((policy.target, policy.minimum, policy.maximum), (6.0, 5.0, 7.0))
        self.assertEqual(policy.as_dict()["profile_overrides"], overrides)

    def test_profile_defaults_record_no_override(self):
        lesson = self._lesson("duration:\n  profile: news\n")
        policy = resolve(lesson)
        self.assertIsNotNone(policy)
        self.assertEqual(policy.profile_overrides(), {})
        defaults = PROFILES["news"]
        self.assertEqual(
            (policy.target, policy.minimum, policy.maximum),
            (defaults["target"], defaults["min"], defaults["max"]),
        )
        self.assertEqual(policy.as_dict()["profile_overrides"], {})

    def test_partial_override_records_only_changed_fields(self):
        lesson = self._lesson(
            "duration:\n  profile: standard\n  target_seconds: 600\n"
        )
        policy = resolve(lesson)
        self.assertIsNotNone(policy)
        overrides = policy.profile_overrides()
        self.assertEqual(list(overrides), ["target_seconds"])
        self.assertEqual(overrides["target_seconds"], {"profile": 1200.0, "declared": 600.0})
        # min/max fall back to the standard profile, unchanged behavior.
        self.assertEqual(policy.minimum, PROFILES["standard"]["min"])
        self.assertEqual(policy.maximum, PROFILES["standard"]["max"])


if __name__ == "__main__":
    unittest.main()