from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.rendering import overlays


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgingHudTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "CodeVideoStudio" / "shots" / "demo"
        self.project.mkdir(parents=True)
        self.scene = self.project / "SPEC.md"
        self.scene.write_text("# SPEC\n", encoding="utf-8")

        hazard = [0.01 * (age % 7) for age in range(91)]
        frames = [
            {
                "population": 10 + step,
                "mean_death_age": None if step == 1 else 20.0 + step,
                "agents": [[0, 0.0, 0.0, step, 1, 2, 0], [1, 0.0, 0.0, step, 0, 9, 0]],
                "hazard": hazard,
            }
            for step in range(3)
        ]
        write_json(
            self.project / "aging.json",
            {
                "schema_version": 2,
                "fps": 30,
                "scenarios": [
                    {"id": "danger", "label": "dangerous world", "frames": frames},
                    {"id": "safe", "label": "safer world", "frames": frames},
                ],
            },
        )
        write_json(
            self.project / "timing.json",
            {"total": 20.0, "segments": [{"id": "s01", "start": 0.0}, {"id": "s08", "start": 12.5}]},
        )

        self.shot = SimpleNamespace(engine="code_video", scene="shots/demo/SPEC.md")
        self.paths = SimpleNamespace(
            storyboard=SimpleNamespace(shots=[self.shot]),
            scene_path=lambda shot: (self.scene, None),
            lesson=SimpleNamespace(compose=SimpleNamespace(overlay="aging_hud")),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_payload_shape(self):
        payload = overlays.build_overlay(self.paths)
        self.assertEqual(payload["kind"], "aging_hud")
        self.assertEqual(payload["title"], "WHY AGING EVOLVES")
        self.assertEqual(payload["split"], 12.5)
        self.assertEqual(payload["total"], 20.0)
        segments = payload["segments"]
        self.assertEqual([segment["id"] for segment in segments], ["danger", "safe"])
        self.assertEqual(segments[0]["start"], 0.0)
        self.assertEqual(segments[0]["end"], 12.5)
        self.assertEqual(segments[1]["start"], 12.5)
        self.assertEqual(len(segments[0]["population"]), 3)
        # 91 yearly hazards bin into ceil(91 / 5) = 19 groups
        self.assertEqual(len(segments[0]["hazard"][0]), 19)

    def test_only_living_agents_count_for_mutation_load(self):
        payload = overlays.build_overlay(self.paths)
        # agent 0 is alive with 2 loci, agent 1 is dead with 9 -> mean is 2.0
        self.assertEqual(payload["segments"][0]["mutation"][0], 2.0)

    def test_null_mean_age_is_preserved(self):
        payload = overlays.build_overlay(self.paths)
        self.assertIsNone(payload["segments"][0]["mean_age"][1])

    def test_no_overlay_declared(self):
        self.paths.lesson.compose.overlay = None
        self.assertIsNone(overlays.build_overlay(self.paths))

    def test_unknown_overlay_kind_is_ignored(self):
        self.paths.lesson.compose.overlay = "not_a_kind"
        self.assertIsNone(overlays.build_overlay(self.paths))


if __name__ == "__main__":
    unittest.main()
