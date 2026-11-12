from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.content.collect import collect
from course_control.content.paths import LessonPaths
from course_control.content.validators import validate

ROOT = Path(__file__).resolve().parents[2]
CLIP = ROOT / "CodeVideoStudio" / "shots" / "attention-flow" / "out" / "final.mp4"

LESSON = {
    "schema_version": 1,
    "lesson_id": "shots-demo",
    "title_en": "Shots demo",
    "title_zh": "镜头模式样片",
    "status": "draft",
    "content": {
        "slides": "slides.md",
        "notes": "lecture_notes.md",
        "storyboard": "storyboard.yaml",
        "assets": "assets/",
    },
    "outputs": {"fps": 30, "resolution": [1920, 1080]},
    "engines": ["code_video"],
    "compose": {"mode": "shots"},
    "production": "authoring/production.yaml",
}

PRODUCTION = {
    "schema_version": 1,
    "lesson": "shots-demo",
    "sequences": [
        {
            "id": "seq-01",
            "title": "one shot",
            "shots": [
                {
                    "id": "shot-001",
                    "duration_s": 30.0,
                    "purpose": "simulate",
                    "visual_type": "population_simulation",
                    "grammar": "simulation",
                    "renderer": "code_video",
                    "source": "CodeVideoStudio/shots/attention-flow/SPEC.md",
                    "transition": {"in": "hard_cut", "out": "dissolve"},
                    "camera": {"movement": "static"},
                }
            ],
        }
    ],
}


class ShotsModeTest(unittest.TestCase):
    def test_collect_and_validate(self) -> None:
        if not CLIP.is_file():
            self.skipTest("attention-flow render is not present")
        with tempfile.TemporaryDirectory() as tmp:
            lesson_dir = Path(tmp) / "shots-demo"
            (lesson_dir / "authoring").mkdir(parents=True)
            (lesson_dir / "lesson.yaml").write_text(
                yaml.safe_dump(LESSON, allow_unicode=True), encoding="utf-8"
            )
            (lesson_dir / "authoring" / "production.yaml").write_text(
                yaml.safe_dump(PRODUCTION, allow_unicode=True), encoding="utf-8"
            )
            build_root = Path(tmp) / "build"
            (build_root / "animation").mkdir(parents=True)
            shutil.copy2(CLIP, build_root / "animation" / "attention-flow.mp4")

            paths = LessonPaths.load(ROOT, lesson_dir, build_root_override=build_root)
            result = validate(paths)
            self.assertEqual([issue.message for issue in result.errors], [])

            shots_file, warnings, outputs = collect(paths)
            self.assertEqual(shots_file.timeline.total_duration_s, 30.0)
            self.assertEqual(len(shots_file.shots), 1)
            shot = shots_file.shots[0]
            self.assertEqual((shot.start_s, shot.duration_s), (0.0, 30.0))
            self.assertEqual(shot.timeline_role, "base")
            self.assertEqual(shot.transition.out, "dissolve")
            self.assertTrue((build_root / "shots.json").is_file())
            payload = json.loads((build_root / "shots.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["shots"][0]["transition"]["in"], "hard_cut")


    def test_word_captions(self) -> None:
        if not CLIP.is_file():
            self.skipTest("attention-flow render is not present")
        lesson = yaml.safe_load(yaml.safe_dump(LESSON))
        lesson["subtitles"] = {
            "enabled": True,
            "mode": "word",
            "position": "low_center",
            "render": "remotion",
        }
        with tempfile.TemporaryDirectory() as tmp:
            lesson_dir = Path(tmp) / "shots-demo"
            (lesson_dir / "authoring").mkdir(parents=True)
            (lesson_dir / "lesson.yaml").write_text(
                yaml.safe_dump(lesson, allow_unicode=True), encoding="utf-8"
            )
            (lesson_dir / "authoring" / "production.yaml").write_text(
                yaml.safe_dump(PRODUCTION, allow_unicode=True), encoding="utf-8"
            )
            build_root = Path(tmp) / "build"
            (build_root / "animation").mkdir(parents=True)
            (build_root / "quality").mkdir(parents=True)
            shutil.copy2(CLIP, build_root / "animation" / "attention-flow.mp4")
            (build_root / "quality" / "asr-alignment.json").write_text(
                json.dumps(
                    {
                        "language": "en",
                        "words": [
                            {"start_ms": 0, "end_ms": 300, "text": "hello"},
                            {"start_ms": 300, "end_ms": 600, "text": "world"},
                            {"start_ms": 600, "end_ms": 900, "text": "again"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            paths = LessonPaths.load(ROOT, lesson_dir, build_root_override=build_root)
            shots_file, _, _ = collect(paths)
            self.assertEqual(shots_file.subtitles["mode"], "word")
            self.assertEqual(shots_file.subtitles["words_count"], 3)
            self.assertTrue((build_root / "subtitles.words.json").is_file())
            timeline = json.loads(
                (build_root / "contracts" / "timeline.spec.json").read_text(encoding="utf-8")
            )
            words = timeline["metadata"]["word_captions"]["words"]
            self.assertEqual([item["text"] for item in words], ["hello", "world", "again"])
            self.assertEqual(timeline["metadata"]["word_captions"]["position"], "low_center")

if __name__ == "__main__":
    unittest.main()
