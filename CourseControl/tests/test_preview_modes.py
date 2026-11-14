from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.design.handoff import apply_design, load_design_map
from course_control.preview.profile import (
    PreviewLevel,
    RenderMode,
    preview_size,
    profile_for,
)
from course_control.preview.runner import run_preview
from course_control.preview.units import plan_lesson_units
from course_control.release.check import INCOMPLETE, run_release_check

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"


class PreviewProfileTest(unittest.TestCase):
    def test_landscape_short_edge_is_480(self) -> None:
        width, height, scale = preview_size(1920, 1080)
        self.assertEqual((width, height), (854, 480))
        self.assertAlmostEqual(scale, 480 / 1080, places=6)

    def test_portrait_short_edge_is_480(self) -> None:
        width, height, _ = preview_size(1080, 1920)
        self.assertEqual((width, height), (480, 854))

    def test_release_is_not_scaled(self) -> None:
        profile = profile_for(
            RenderMode.RELEASE, PreviewLevel.PROJECT, width=1920, height=1080, fps=30
        )
        self.assertEqual((profile.width, profile.height), (1920, 1080))
        self.assertEqual(profile.scale, 1.0)
        self.assertFalse(profile.is_preview)

    def test_preview_keeps_fps(self) -> None:
        profile = profile_for(
            RenderMode.PREVIEW, PreviewLevel.SHOT, width=1920, height=1080, fps=24
        )
        self.assertEqual(profile.fps, 24)
        self.assertEqual(profile.width, 854)


class PreviewUnitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.build = Path(self._tmp.name)
        self.paths = LessonPaths.load(
            WORKSPACE,
            FIXTURE,
            build_root_override=self.build,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_storyboard_becomes_one_unit(self) -> None:
        units = plan_lesson_units(self.paths, PreviewLevel.SHOT)
        self.assertEqual([unit.id for unit in units], ["shot_001"])
        self.assertEqual(units[0].engine, "blender")
        self.assertEqual(units[0].duration_s, 1.0)
        self.assertEqual(units[0].segment, "part-01")

    def test_design_is_attached_to_the_unit(self) -> None:
        design_dir = self.build / "design"
        design_dir.mkdir(parents=True)
        (design_dir / "visual_design.json").write_text(
            json.dumps(
                {
                    "shots": [
                        {
                            "shot_id": "shot_001",
                            "composition": {"focal_point": [0.35, 0.47]},
                            "motion": {"camera": "slow push in"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        units = plan_lesson_units(self.paths, PreviewLevel.SHOT)
        self.assertIsNotNone(units[0].design)
        self.assertEqual(units[0].design["motion"]["camera"], "slow push in")

    def test_selection_filters_by_shot_and_segment(self) -> None:
        self.assertEqual(
            plan_lesson_units(self.paths, PreviewLevel.SHOT, {"shot_001"})[0].id,
            "shot_001",
        )
        self.assertEqual(
            plan_lesson_units(self.paths, PreviewLevel.SEGMENT, {"part-01"})[0].id,
            "shot_001",
        )
        self.assertEqual(
            plan_lesson_units(self.paths, PreviewLevel.SHOT, {"missing"}), []
        )


class DesignHandoffTest(unittest.TestCase):
    def test_apply_design_does_not_overwrite_an_existing_document(self) -> None:
        from course_control.content.contracts import ShotSpec, Storyboard

        spec = ShotSpec(
            id="shot_001",
            slide=1,
            engine="manim",
            scene="scene.py::Scene",
            cue_seconds=0.0,
            expected_duration_s=2.0,
        )
        storyboard = Storyboard(lesson="demo", shots=[spec])
        designed, changed = apply_design(storyboard, {"shot_001": {"motion": {"camera": "pan right"}}})
        self.assertEqual(changed, ["shot_001"])
        self.assertEqual(designed.shots[0].design["motion"]["camera"], "pan right")
        again, changed_again = apply_design(designed, {"shot_001": {"motion": {"camera": "pull out"}}})
        self.assertEqual(changed_again, [])
        self.assertEqual(again.shots[0].design["motion"]["camera"], "pan right")

    def test_load_design_map_ignores_malformed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "design" / "visual_design.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"shots": [{"shot_id": "a"}, {"nope": 1}, "bad"]}),
                encoding="utf-8",
            )
            self.assertEqual(load_design_map(Path(tmp)), {"a": {"shot_id": "a"}})


class TopicProjectTest(unittest.TestCase):
    def test_topic_plan_carries_segments_and_licences(self) -> None:
        import yaml
        from course_control.preview.topic import load_topic

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            project_dir = workspace / "projects" / "demo-topic"
            project_dir.mkdir(parents=True)
            (project_dir / "project.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "project": {
                            "id": "demo-topic",
                            "mode": "topic_video",
                            "title": "Demo",
                            "language": "en",
                        },
                        "input": {"topic": "demo"},
                        "production": {
                            "topic_video": {
                                "target_seconds": 20,
                                "entry": "src/demo/index.ts",
                                "composition": "Demo",
                                "output": "demo.mp4",
                                "delivery_dir": "deliver/demo",
                                "shots": [
                                    {"id": "a", "start_s": 0, "end_s": 10, "segment": "part"},
                                    {"id": "b", "start_s": 10, "end_s": 20, "segment": "part"},
                                ],
                                "segments": [
                                    {"id": "part", "start_s": 0, "end_s": 20}
                                ],
                                "licences": [
                                    {
                                        "asset": "music",
                                        "status": "cc_by",
                                        "attribution": "Track — Artist, CC BY 3.0",
                                        "commercial_allowed": True,
                                    }
                                ],
                            }
                        },
                        "media": {"resolution": "1080x1920", "frame_rate": 30},
                    }
                ),
                encoding="utf-8",
            )
            context = load_topic(workspace, project_dir / "project.yaml")
            self.assertEqual(context.project_id, "demo-topic")
            self.assertEqual(context.width, 1080)
            self.assertEqual(context.height, 1920)
            self.assertEqual(len(context.plan.shots), 2)
            self.assertEqual(context.delivery_dir, (workspace / "deliver/demo").resolve())

    def test_unknown_licence_is_not_a_pass(self) -> None:
        from course_control.release.check import _topic_steps

        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "missing.mp4"
            steps = _topic_steps(Path(tmp), video, [{"asset": "music", "status": "unknown"}])
            self.assertEqual(steps[0].id, "final_video")
            self.assertEqual(steps[0].status, "incomplete")


class ReleaseCheckTest(unittest.TestCase):
    def test_missing_final_video_is_incomplete_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            paths = LessonPaths.load(WORKSPACE, FIXTURE, build_root_override=build)
            payload = run_release_check(WORKSPACE, paths=paths)
            self.assertEqual(payload["status"], INCOMPLETE)
            self.assertFalse(payload["delivery_allowed"])
            self.assertEqual(payload["steps"][0]["id"], "final_video")


class PreviewRunTest(unittest.TestCase):
    def test_render_refuses_to_invent_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            paths = LessonPaths.load(WORKSPACE, FIXTURE, build_root_override=build)
            profile = profile_for(
                RenderMode.PREVIEW, PreviewLevel.SHOT, width=1920, height=1080, fps=30
            )
            with self.assertRaises(ValueError):
                run_preview(
                    paths,
                    level=PreviewLevel.SHOT,
                    profile=profile,
                    selection={"missing"},
                )


if __name__ == "__main__":
    unittest.main()
