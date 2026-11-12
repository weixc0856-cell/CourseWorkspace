from __future__ import annotations

import unittest

from course_control.direction.beats import Beat, BeatSheet, BeatShot, validate_sheet
from course_control.rendering.grammar import default_registry, load_registry

SEGMENTS = [(0.0, 6.0), (6.0, 6.0)]


def shot(shot_id: str, grammar: str, start: float, end: float, long_lived=()) -> BeatShot:
    return BeatShot(
        id=shot_id,
        segment=1 if shot_id.startswith("a") else 2,
        grammar=grammar,
        start=start,
        end=end,
        engine="code_video",
        long_lived=list(long_lived),
        beats=[
            Beat(at=0.1, kind="reveal", action="first change"),
            Beat(at=0.6, kind="highlight", action="second change"),
        ],
    )


class GrammarRegistryTest(unittest.TestCase):
    def test_default_registry_has_long_take(self) -> None:
        registry = default_registry()
        self.assertIn("long_take", registry.grammars)
        self.assertEqual(registry.get("long_take").shot_seconds.min, 5.0)

    def test_workspace_registry_has_multiple_grammars(self) -> None:
        from pathlib import Path

        registry = load_registry(Path(__file__).resolve().parents[2])
        for name in ("long_take", "kinetic_edit", "simulation", "kinetic_type"):
            self.assertTrue(registry.has(name), name)


class GrammarAwareBeatsTest(unittest.TestCase):
    def test_three_second_cuts_pass_under_kinetic(self) -> None:
        sheet = BeatSheet(
            lesson="demo",
            grammar="kinetic_edit",
            subtitle_safe_below=-2.2,
            shots=[
                shot("a1", "kinetic_edit", 0.0, 0.5),
                shot("a2", "kinetic_edit", 0.5, 1.0),
                shot("b1", "kinetic_edit", 0.0, 0.5),
                shot("b2", "kinetic_edit", 0.5, 1.0),
            ],
        )
        self.assertEqual(validate_sheet(sheet, SEGMENTS, registry=default_registry_for_test()), [])

    def test_three_second_cuts_fail_under_long_take(self) -> None:
        sheet = BeatSheet(
            lesson="demo",
            grammar="long_take",
            subtitle_safe_below=-2.2,
            shots=[
                shot("a1", "long_take", 0.0, 0.5),
                shot("a2", "long_take", 0.5, 1.0),
                shot("b1", "long_take", 0.0, 0.5),
                shot("b2", "long_take", 0.5, 1.0),
            ],
        )
        issues = validate_sheet(sheet, SEGMENTS, registry=default_registry_for_test())
        self.assertTrue(any("shorter than" in issue for issue in issues))

    def test_kinetic_does_not_require_long_lived(self) -> None:
        sheet = BeatSheet(
            lesson="demo",
            grammar="kinetic_edit",
            subtitle_safe_below=-2.2,
            shots=[
                shot("a1", "kinetic_edit", 0.0, 0.5),
                shot("a2", "kinetic_edit", 0.5, 1.0),
                shot("b1", "kinetic_edit", 0.0, 0.5),
                shot("b2", "kinetic_edit", 0.5, 1.0),
            ],
        )
        issues = validate_sheet(sheet, SEGMENTS, registry=default_registry_for_test())
        self.assertFalse(any("continuity" in issue for issue in issues))


def default_registry_for_test():
    from course_control.rendering.grammar import GrammarConstraints, GrammarRegistry, GrammarSpec, ShotWindow

    return GrammarRegistry(
        grammars={
            "long_take": GrammarSpec(
                label="long",
                shot_seconds=ShotWindow(min=5.0, max=16.0),
                constraints=GrammarConstraints(
                    first_action_by=0.35,
                    max_action_gap_s=4.0,
                    long_lived_ratio_min=0.5,
                    camera_motive_required=True,
                    min_actions=2,
                ),
            ),
            "kinetic_edit": GrammarSpec(
                label="kinetic",
                shot_seconds=ShotWindow(min=1.5, max=8.0),
                constraints=GrammarConstraints(
                    first_action_by=0.5,
                    max_action_gap_s=8.0,
                    long_lived_ratio_min=0.0,
                    camera_motive_required=False,
                    min_actions=1,
                ),
            ),
        }
    )


if __name__ == "__main__":
    unittest.main()
