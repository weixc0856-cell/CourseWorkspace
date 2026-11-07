from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATH = ROOT / "ManimSandbox" / "05-multi-head" / "multi_head_math.py"
SCRIPT = ROOT / "ManimSandbox" / "05-multi-head" / "verify_math.py"

spec = importlib.util.spec_from_file_location("multi_head_math", MATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {MATH}")
mh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mh)


class MultiHeadMathTest(unittest.TestCase):
    def setUp(self):
        self.report = mh.compute()

    def test_all_checks_pass(self):
        self.assertTrue(self.report["all_ok"])
        self.assertTrue(all(check["ok"] for check in self.report["checks"]))
        ids = [check["id"] for check in self.report["checks"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_dimensions(self):
        dims = self.report["dimensions"]
        self.assertEqual(dims["tokens"], 4)
        self.assertEqual(dims["d_model"], 4)
        self.assertEqual(dims["heads"], 2)
        self.assertEqual(dims["d_k"], 2)
        self.assertEqual(dims["d_v"], 2)
        self.assertEqual(dims["concat_width"], 4)
        self.assertEqual(mh._shape(self.report["heads"][0]["q"]), (4, 2))
        self.assertEqual(mh._shape(self.report["heads"][0]["alpha"]), (4, 4))
        self.assertEqual(mh._shape(self.report["concat"]), (4, 4))
        self.assertEqual(mh._shape(self.report["final"]), (4, 4))

    def test_alpha_rows_sum_to_one(self):
        for head in self.report["heads"]:
            for row in head["alpha"]:
                self.assertAlmostEqual(sum(row), 1.0, places=12)

    def test_each_head_focuses_a_different_token(self):
        head1 = self.report["heads"][0]["alpha"][mh.QUERY_INDEX]
        head2 = self.report["heads"][1]["alpha"][mh.QUERY_INDEX]
        self.assertEqual(max(range(len(head1)), key=head1.__getitem__), 0)
        self.assertEqual(max(range(len(head2)), key=head2.__getitem__), 2)

    def test_concat_is_column_concatenation(self):
        head1 = self.report["heads"][0]["context"]
        head2 = self.report["heads"][1]["context"]
        for row, values in enumerate(self.report["concat"]):
            self.assertEqual(values[:2], head1[row])
            self.assertEqual(values[2:], head2[row])

    def test_output_projection_changes_concat(self):
        self.assertNotEqual(self.report["final"], self.report["concat"])

    def test_deterministic(self):
        self.assertEqual(mh.compute(), mh.compute())

    def test_script_writes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "math-report.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["all_ok"])
            self.assertEqual(payload["kind"], "e6_5_math_report")


if __name__ == "__main__":
    unittest.main()
