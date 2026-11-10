from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.adapters.remotion import _render_props


def lesson(render: str = "remotion") -> SimpleNamespace:
    return SimpleNamespace(
        subtitles=SimpleNamespace(enabled=True, render=render)
    )


class RenderPropsTest(unittest.TestCase):
    def test_timeline_assets_are_build_root_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            build_root = workspace / "build" / "_isolated" / "demo"
            timeline = build_root / "contracts" / "timeline.spec.json"
            timeline.parent.mkdir(parents=True)
            timeline.write_text(
                json.dumps(
                    {
                        "lesson_id": "demo",
                        "video": [
                            {
                                "asset": {
                                    "path": "build/_isolated/demo/animation/shot.mp4"
                                }
                            }
                        ],
                        "audio": [
                            {
                                "asset": {
                                    "path": "build/_isolated/demo/narration/narration.wav"
                                }
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            paths = SimpleNamespace(
                workspace=workspace,
                build_root=build_root,
                lesson=lesson(),
            )
            target = _render_props(paths, timeline, True, build_root / "shots.json")
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["video"][0]["asset"]["path"], "animation/shot.mp4")
            self.assertEqual(
                data["audio"][0]["asset"]["path"], "narration/narration.wav"
            )
            self.assertEqual(target, build_root / "final" / "render-props.json")

    def test_burn_in_disables_captions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            build_root = workspace / "build" / "demo"
            timeline = build_root / "contracts" / "timeline.spec.json"
            timeline.parent.mkdir(parents=True)
            timeline.write_text('{"video": [], "audio": []}', encoding="utf-8")
            paths = SimpleNamespace(
                workspace=workspace,
                build_root=build_root,
                lesson=lesson("burn_in"),
            )
            target = _render_props(paths, timeline, True, build_root / "shots.json")
            self.assertFalse(json.loads(target.read_text(encoding="utf-8"))["captions"])

    def test_shots_mode_without_burn_in_uses_shots_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            build_root = workspace / "build" / "demo"
            shots = build_root / "shots.json"
            shots.parent.mkdir(parents=True)
            shots.write_text("{}", encoding="utf-8")
            paths = SimpleNamespace(
                workspace=workspace,
                build_root=build_root,
                lesson=lesson(),
            )
            self.assertEqual(
                _render_props(paths, build_root / "timeline.json", False, shots), shots
            )


if __name__ == "__main__":
    unittest.main()
