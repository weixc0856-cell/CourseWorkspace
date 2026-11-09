from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path

from course_control.collect import collect
from course_control.contracts import LessonConfig, ShotSpec

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


class SceneCollectTest(unittest.TestCase):
    def test_scene_base_file_skips_storyboard_overlays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text(NOTES, encoding="utf-8")
            (root / "scenes").mkdir()
            (root / "scenes" / "base.mp4").write_bytes(b"fake")
            (root / "scenes" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "lesson": "scene-fixture",
                        "base_file": "scenes/base.mp4",
                        "pages": [
                            {"slide": 1, "file": "scenes/base.mp4"},
                            {"slide": 2, "file": "scenes/base.mp4"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            lesson = LessonConfig.model_validate(
                {
                    "schema_version": 1,
                    "lesson_id": "scene-fixture",
                    "title_en": "Scene fixture",
                    "title_zh": "镜头夹具",
                    "status": "draft",
                    "content": {"slides": "slides.md", "notes": "notes.md", "storyboard": "storyboard.yaml", "assets": "assets/"},
                    "outputs": {"fps": 30, "resolution": [1920, 1080]},
                    "engines": ["manim"],
                    "compose": {"mode": "scene"},
                    "narration": {"enabled": False},
                    "subtitles": {"enabled": False},
                }
            )
            overlay = ShotSpec(
                id="missing_overlay",
                slide=1,
                engine="manim",
                scene="missing.py::Missing",
                cue_seconds=0.0,
            )
            paths = types.SimpleNamespace(
                lesson=lesson,
                build_root=root,
                workspace=root,
                slug="scene-fixture",
                content_path=lambda rel: root / rel,
                storyboard=types.SimpleNamespace(shots=[overlay], annotations=[]),
            )
            shots_file, _warnings, _outputs = collect(paths)
            shots = shots_file.shots
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0].source, "scenes/base.mp4")
        self.assertEqual(shots[0].timeline_role, "base")

    def test_scene_manifest_becomes_full_frame_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text(NOTES, encoding="utf-8")
            (root / "scenes").mkdir()
            for slide in (1, 2):
                (root / "scenes" / f"scene-{slide:03d}.mp4").write_bytes(b"fake")
            (root / "scenes" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "lesson": "scene-fixture",
                        "pages": [
                            {"slide": 1, "file": "scenes/scene-001.mp4", "duration_s": 60},
                            {"slide": 2, "file": "scenes/scene-002.mp4", "duration_s": 90},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            lesson = LessonConfig.model_validate(
                {
                    "schema_version": 1,
                    "lesson_id": "scene-fixture",
                    "title_en": "Scene fixture",
                    "title_zh": "镜头夹具",
                    "status": "draft",
                    "content": {"slides": "slides.md", "notes": "notes.md", "storyboard": "storyboard.yaml", "assets": "assets/"},
                    "outputs": {"fps": 30, "resolution": [1920, 1080]},
                    "engines": ["manim"],
                    "compose": {"mode": "scene"},
                    "narration": {"enabled": False},
                    "subtitles": {"enabled": False},
                }
            )
            paths = types.SimpleNamespace(
                lesson=lesson,
                build_root=root,
                workspace=root,
                slug="scene-fixture",
                content_path=lambda rel: root / rel,
                storyboard=types.SimpleNamespace(shots=[], annotations=[]),
            )
            shots_file, _warnings, _outputs = collect(paths)
            shots = shots_file.shots
        self.assertEqual([shot.kind for shot in shots], ["animation", "animation"])
        self.assertEqual(shots[0].source, "scenes/scene-001.mp4")
        self.assertEqual(shots[0].timeline_role, "base")
        self.assertEqual(shots[1].duration_s, 90.0)


if __name__ == "__main__":
    unittest.main()
