from __future__ import annotations

import json
import unittest
from pathlib import Path

from course_control.contracts import LessonConfig, Storyboard

WORKSPACE = Path(__file__).resolve().parents[2]


class LegacySchemaSyncTest(unittest.TestCase):
    def test_lesson_schema_matches_model(self):
        path = WORKSPACE / "shared" / "schemas" / "lesson.schema.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), LessonConfig.model_json_schema())

    def test_storyboard_schema_matches_model(self):
        path = WORKSPACE / "shared" / "schemas" / "storyboard.schema.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), Storyboard.model_json_schema())


if __name__ == "__main__":
    unittest.main()
