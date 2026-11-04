from __future__ import annotations

import unittest

from scene_expr import ExpressionError, compile_expression


class ExpressionTest(unittest.TestCase):
    def test_evaluates_whitelisted_expression(self):
        compiled = compile_expression("sin(x) * cos(y) + z")
        self.assertAlmostEqual(compiled(0.0, 0.0, 1.0), 1.0)
        self.assertAlmostEqual(compiled(1.0, 0.0, 0.0), 0.8414709848, places=6)

    def test_min_max_and_unary(self):
        compiled = compile_expression("max(-x, min(y, 2))")
        self.assertEqual(compiled(3.0, 5.0, 0.0), 2.0)

    def test_rejects_import_and_calls(self):
        for expression in (
            "__import__('os')",
            "open('x')",
            "eval('1')",
            "x.__class__",
            "x[0]",
            "lambda: 1",
            "x if y else z",
            "x and y",
        ):
            with self.subTest(expression=expression), self.assertRaises(ExpressionError):
                compile_expression(expression)

    def test_rejects_unknown_names_and_operators(self):
        with self.assertRaises(ExpressionError):
            compile_expression("w + 1")
        with self.assertRaises(ExpressionError):
            compile_expression("x << 2")

    def test_rejects_oversized_expression(self):
        with self.assertRaises(ExpressionError):
            compile_expression("x + " * 80 + "1")

    def test_rejects_non_finite_evaluation(self):
        with self.assertRaises(ExpressionError):
            compile_expression("exp(1000)")(0.0, 0.0, 0.0)
        with self.assertRaises(ExpressionError):
            compile_expression("1 / x")(0.0, 0.0, 0.0)

    def test_rejects_domain_error(self):
        with self.assertRaises(ExpressionError):
            compile_expression("sqrt(x)")(-1.0, 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
