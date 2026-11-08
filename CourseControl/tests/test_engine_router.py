from __future__ import annotations

import unittest

from course_control.engine_router import VisualRequirement, route_engine


class RouteTest(unittest.TestCase):
    def test_math_goes_to_manim(self):
        route = route_engine(VisualRequirement(kind="matrix"))
        self.assertEqual(route.engine, "manim")
        self.assertEqual(route.profile, "math_explainer")

    def test_three_d_goes_to_blender(self):
        route = route_engine(VisualRequirement(kind="structure3d", needs_3d=True))
        self.assertEqual(route.engine, "blender")
        self.assertEqual(route.profile, "engineering_3d")

    def test_engineering_kind_goes_to_blender(self):
        route = route_engine(VisualRequirement(kind="mechanical"))
        self.assertEqual(route.engine, "blender")

    def test_layout_goes_to_remotion(self):
        route = route_engine(VisualRequirement(kind="title"))
        self.assertEqual(route.engine, "remotion")

    def test_chart_goes_to_remotion(self):
        self.assertEqual(route_engine(VisualRequirement(kind="chart")).engine, "remotion")

    def test_existing_motion_asset_is_kept(self):
        route = route_engine(
            VisualRequirement(kind="matrix", has_existing_motion_asset=True)
        )
        self.assertEqual(route.engine, "motion_canvas")
        self.assertEqual(route.profile, "legacy")

    def test_motion_graphics_goes_to_code_video(self):
        route = route_engine(VisualRequirement(kind="motion_graphics"))
        self.assertEqual(route.engine, "code_video")
        self.assertEqual(route.profile, "code_video")

    def test_svg_goes_to_code_video(self):
        self.assertEqual(route_engine(VisualRequirement(kind="svg")).engine, "code_video")

    def test_threejs_without_3d_flag_goes_to_code_video(self):
        self.assertEqual(route_engine(VisualRequirement(kind="threejs")).engine, "code_video")

    def test_unknown_kind_defaults_to_manim(self):
        route = route_engine(VisualRequirement(kind="explain"))
        self.assertEqual(route.engine, "manim")

    def test_needs_3d_overrides_kind(self):
        route = route_engine(VisualRequirement(kind="diagram", needs_3d=True))
        self.assertEqual(route.engine, "blender")


if __name__ == "__main__":
    unittest.main()
