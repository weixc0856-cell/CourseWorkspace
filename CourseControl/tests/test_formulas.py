from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from course_control.rendering.formula_video_qc import image_similarity
from course_control.content.validators import formula_binding_problems
from course_control.rendering.formulas import (
    FormulaSource,
    FormulaSpec,
    audit_formula,
    math_problems,
    render_formula,
    source_problems,
)

WORKSPACE = Path(__file__).resolve().parents[2]


def spec(latex: str, **overrides) -> FormulaSpec:
    values = dict(
        formula_id="TEST-001",
        latex=latex,
        display="block",
        meaning="test formula",
        symbols={"x": "变量"},
        source=FormulaSource(document="test source", locator="§1"),
    )
    values.update(overrides)
    return FormulaSpec(**values)


class FormulaSourceTest(unittest.TestCase):
    def test_valid_formula_has_no_source_issues(self):
        self.assertEqual(source_problems(spec(r"C_D=\frac{F_D}{\frac12\rho U_\infty^2 A}")), [])

    def test_unescaped_percent_is_error(self):
        issues = source_problems(spec(r"P/P_0=80% \quad \text{pressure ratio}"))
        self.assertTrue(any("unescaped" in issue.message for issue in issues))

    def test_escaped_percent_is_allowed(self):
        self.assertFalse(
            any(
                "unescaped" in issue.message
                for issue in source_problems(spec(r"P/P_0=80\%"))
            )
        )

    def test_unbalanced_brace_is_error(self):
        issues = source_problems(spec(r"\frac{1}{2"))
        self.assertTrue(any("brace" in issue.message for issue in issues))

    def test_full_document_commands_are_rejected(self):
        issues = source_problems(spec(r"\documentclass{article} x=1"))
        self.assertTrue(any("forbidden" in issue.message for issue in issues))

    def test_math_check_catches_false_identity(self):
        issues = math_problems(spec(r"a^2 - b^2 = a^2 + b^2"))
        self.assertTrue(any(issue.level == "error" for issue in issues))


class FormulaBindingTest(unittest.TestCase):
    def test_unknown_and_unreferenced_ids_are_reported(self):
        import json
        import types

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = FormulaSpec(
                formula_id="VEC-001",
                latex=r"\mathbf{a}+\mathbf{b}=\mathbf{b}+\mathbf{a}",
                meaning="vector commutativity",
                symbols={"a": "vector"},
                source=FormulaSource(document="test", locator="§1"),
            )
            (root / "VEC-001.json").write_text(
                json.dumps(spec.model_dump(mode="json")), encoding="utf-8"
            )
            shots = [
                types.SimpleNamespace(id="shot_1", formula_ids=["VEC-999"]),
            ]
            problems = formula_binding_problems(shots, root)
            self.assertTrue(any("unknown formula_id" in item for item in problems))
            self.assertTrue(any("not referenced" in item for item in problems))

    def test_valid_binding_has_no_problems(self):
        import json
        import types

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = FormulaSpec(
                formula_id="VEC-001",
                latex=r"\mathbf{a}+\mathbf{b}=\mathbf{b}+\mathbf{a}",
                meaning="vector commutativity",
                symbols={"a": "vector"},
                source=FormulaSource(document="test", locator="§1"),
            )
            (root / "VEC-001.json").write_text(
                json.dumps(spec.model_dump(mode="json")), encoding="utf-8"
            )
            problems = formula_binding_problems(
                [types.SimpleNamespace(id="shot_1", formula_ids=["VEC-001"])], root
            )
            self.assertEqual(problems, [])


class FormulaVideoQCImageTest(unittest.TestCase):
    def test_identical_edge_maps_score_high(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.png"
            b = Path(tmp) / "b.png"
            for path in (a, b):
                image = Image.new("RGB", (200, 100), "white")
                draw = ImageDraw.Draw(image)
                draw.rectangle([30, 30, 170, 70], outline="black", width=4)
                draw.line([40, 50, 160, 50], fill="black", width=3)
                image.save(path)
            self.assertGreater(image_similarity(a, b), 0.9)

    def test_blank_crop_scores_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            formula = Path(tmp) / "formula.png"
            blank = Path(tmp) / "blank.png"
            image = Image.new("RGB", (200, 100), "white")
            ImageDraw.Draw(image).rectangle([30, 30, 170, 70], outline="black", width=4)
            image.save(formula)
            Image.new("RGB", (200, 100), "white").save(blank)
            self.assertLess(image_similarity(formula, blank), 0.2)


@unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is required for LaTeX compile checks")
class FormulaRenderTest(unittest.TestCase):
    def test_render_percent_and_greek(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            payload = render_formula(
                spec(r"\frac{P}{P_0}=80\% \quad \rho,\mu,\alpha,\beta,\omega"),
                out,
                WORKSPACE,
            )
            self.assertTrue(Path(payload["png"]).is_file())
            self.assertGreater(payload["width"], 20)
            self.assertFalse(payload["invisible_glyphs"])
            self.assertTrue((out / "render" / "formula.html").is_file())

    def test_audit_records_compile_and_visual_without_claiming_math_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit_formula(spec(r"E=mc^2"), Path(tmp), WORKSPACE)
            self.assertEqual(result.validation.latex_compile, "pass")
            self.assertEqual(result.validation.visual_review, "pass")
            self.assertEqual(result.validation.mathematical_review, "pending")
            self.assertTrue((Path(tmp) / "formula.audit.json").is_file())


if __name__ == "__main__":
    unittest.main()
