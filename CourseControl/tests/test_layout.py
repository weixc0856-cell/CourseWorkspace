from __future__ import annotations

import unittest

from course_control.rendering.layout import (
    DESIGN,
    TEMPLATES,
    LayoutTemplate,
    Region,
    TemplateConstraints,
    choose_template,
    get_template,
    ok,
    validate_content,
    validate_template,
)
from course_control.rendering.layout.schema import Region as R


class LayoutLibraryTest(unittest.TestCase):
    def test_all_templates_pass_static_checks(self):
        for template in TEMPLATES.values():
            checks = validate_template(template, DESIGN)
            self.assertTrue(ok(checks), (template.id, [c.message for c in checks]))

    def test_template_lookup_and_mapping(self):
        self.assertEqual(get_template("process_flow").id, "process_flow")
        self.assertEqual(choose_template("diagram", "cross_attention_flow"), "process_flow")
        self.assertEqual(choose_template("chart"), "data_chart")
        self.assertEqual(choose_template("recap"), "summary")
        with self.assertRaises(KeyError):
            get_template("nope")

    def test_overlap_is_rejected(self):
        template = LayoutTemplate(
            id="bad_overlap",
            name="bad",
            content_type="principle",
            regions=[
                R(role="title", x=0.06, y=0.80, w=0.88, h=0.10),
                R(role="main_visual", x=0.06, y=0.30, w=0.60, h=0.40),
                R(role="explanation", x=0.50, y=0.30, w=0.40, h=0.40),
            ],
        )
        rules = {check.id for check in validate_template(template)}
        self.assertIn("layout.overlap", rules)

    def test_small_visual_is_rejected(self):
        template = LayoutTemplate(
            id="bad_visual",
            name="bad",
            content_type="process",
            regions=[
                R(role="title", x=0.06, y=0.80, w=0.88, h=0.10),
                R(role="main_visual", x=0.40, y=0.40, w=0.20, h=0.20),
            ],
            constraints=TemplateConstraints(min_main_visual_area=0.30),
        )
        rules = {check.id for check in validate_template(template)}
        self.assertIn("layout.visual_area", rules)

    def test_safe_margin_is_enforced(self):
        template = LayoutTemplate(
            id="bad_margin",
            name="bad",
            content_type="process",
            regions=[
                R(role="title", x=0.01, y=0.80, w=0.60, h=0.10),
                R(role="main_visual", x=0.06, y=0.20, w=0.80, h=0.50),
            ],
        )
        rules = {check.id for check in validate_template(template)}
        self.assertIn("layout.safe_margin", rules)

    def test_capacity_checks(self):
        template = get_template("process_flow")
        checks = validate_content(template, title_chars=500, body_chars=0)
        self.assertIn("layout.title_capacity", {check.id for check in checks})
        checks = validate_content(template, title_chars=10, bullet_count=6)
        self.assertIn("layout.bullets", {check.id for check in checks})


if __name__ == "__main__":
    unittest.main()
