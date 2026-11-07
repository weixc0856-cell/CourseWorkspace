from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path

from course_control.collect import _page_timing, _write_page_plan
from course_control.contracts import LessonConfig


def lesson(timing: str = "planned", duration: dict | None = None) -> LessonConfig:
    payload = {
        "schema_version": 1,
        "lesson_id": "timing-fixture",
        "title_en": "Timing fixture",
        "title_zh": "时间夹具",
        "status": "draft",
        "content": {
            "slides": "slides.md",
            "notes": "lecture_notes.md",
            "storyboard": "storyboard.yaml",
            "assets": "assets/",
        },
        "outputs": {"fps": 30, "resolution": [1920, 1080]},
        "engines": ["manim"],
        "compose": {"mode": "deck"},
        "narration": {"enabled": True, "source": "narration.wav", "timing": timing},
    }
    if duration is not None:
        payload["duration"] = duration
    return LessonConfig.model_validate(payload)


NOTES = """### Slide 1: One

- **时长预算**：60 秒
- **动画切入**：无
- **技术核查**：none
- **逐字口播**：One.

### Slide 2: Two

- **时长预算**：90 秒
- **动画切入**：无
- **技术核查**：none
- **逐字口播**：Two.
"""


def fake_paths(build_root: Path, timing: str, duration: dict | None = None):
    return types.SimpleNamespace(
        lesson=lesson(timing, duration),
        build_root=build_root,
        slug="timing-fixture",
    )


class PageTimingTest(unittest.TestCase):
    def test_planned_uses_notes_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = fake_paths(Path(tmp), "planned")
            budgets, starts, timing, pages = _page_timing(paths, NOTES)
        self.assertEqual(budgets, [60.0, 90.0])
        self.assertEqual(starts, [0.0, 60.0])
        self.assertEqual(timing, "planned")
        self.assertEqual(pages[1]["start_s"], 60.0)

    def test_measured_uses_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            (build / "narration").mkdir()
            (build / "narration" / "narration.meta.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {"slide": 1, "measured_s": 55.0},
                            {"slide": 2, "measured_s": 100.0},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            paths = fake_paths(build, "measured")
            budgets, starts, timing, pages = _page_timing(paths, NOTES)
        self.assertEqual(budgets, [55.0, 100.0])
        self.assertEqual(starts, [0.0, 55.0])
        self.assertEqual(timing, "measured")
        self.assertEqual(pages[1]["drift_s"], 10.0)

    def test_measured_without_meta_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = fake_paths(Path(tmp), "measured")
            with self.assertRaises(Exception):
                _page_timing(paths, NOTES)

    def test_measured_page_count_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            (build / "narration").mkdir()
            (build / "narration" / "narration.meta.json").write_text(
                json.dumps({"pages": [{"slide": 1, "measured_s": 55.0}]}),
                encoding="utf-8",
            )
            paths = fake_paths(build, "measured")
            with self.assertRaises(Exception):
                _page_timing(paths, NOTES)

    def test_page_plan_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            paths = fake_paths(build, "planned", {"profile": "news", "target_seconds": 150})
            path = _write_page_plan(
                paths,
                "planned",
                [{"slide": 1, "start_s": 0.0, "duration_s": 150.0}],
                150.0,
            )
            self.assertIsNotNone(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["timing"], "planned")
            self.assertEqual(data["total_s"], 150.0)

    def test_measured_outside_window_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = fake_paths(
                Path(tmp), "measured", {"profile": "standard", "target_seconds": 1200}
            )
            with self.assertRaises(Exception):
                _write_page_plan(paths, "measured", [], 900.0)


if __name__ == "__main__":
    unittest.main()
