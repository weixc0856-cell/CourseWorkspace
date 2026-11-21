from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.release.check import (
    NOT_RUN,
    PASS,
    TOKEN_BILL_BASELINE,
    WARN,
    Step,
    _overall,
    _token_bill_step,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "analyze_session_tokens.py"


def _paths(root: Path, slug: str = "t1-01") -> SimpleNamespace:
    return SimpleNamespace(slug=slug, build_root=root / "build" / slug)


def _write_bill(paths, cost, *, api_calls=10):
    logs = paths.build_root.parent / "_logs"
    logs.mkdir(parents=True, exist_ok=True)
    bill = logs / f"token-bill-{paths.slug}.json"
    bill.write_text(
        json.dumps({"cost_weighted": cost, "api_calls": api_calls}), encoding="utf-8"
    )
    return bill


class TokenBillGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.paths = _paths(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_bill_is_not_run(self):
        step = _token_bill_step(self.paths)
        self.assertEqual(step.id, "token_bill")
        self.assertEqual(step.status, NOT_RUN)
        self.assertNotEqual(step.status, PASS)
        self.assertIsNone(step.data["cost_weighted"])

    def test_over_baseline_without_note_warns(self):
        _write_bill(self.paths, TOKEN_BILL_BASELINE + 1)
        step = _token_bill_step(self.paths)
        self.assertEqual(step.status, WARN)
        self.assertIn("baseline", step.detail)

    def test_over_baseline_with_note_passes(self):
        _write_bill(self.paths, TOKEN_BILL_BASELINE + 1)
        logs = self.paths.build_root.parent / "_logs"
        (logs / f"token-bill-{self.paths.slug}-note.md").write_text("why", encoding="utf-8")
        step = _token_bill_step(self.paths)
        self.assertEqual(step.status, PASS)

    def test_under_baseline_passes(self):
        _write_bill(self.paths, TOKEN_BILL_BASELINE - 1)
        step = _token_bill_step(self.paths)
        self.assertEqual(step.status, PASS)

    def test_malformed_bill_is_not_run(self):
        logs = self.paths.build_root.parent / "_logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"token-bill-{self.paths.slug}.json").write_text("{not json", encoding="utf-8")
        step = _token_bill_step(self.paths)
        self.assertEqual(step.status, NOT_RUN)

    def test_non_numeric_cost_is_not_run(self):
        _write_bill(self.paths, "lots")
        step = _token_bill_step(self.paths)
        self.assertEqual(step.status, NOT_RUN)

    def test_warn_and_not_run_do_not_block_overall(self):
        steps = [
            Step("a", PASS),
            Step("token_bill", WARN),
            Step("other", NOT_RUN),
        ]
        self.assertEqual(_overall(steps), PASS)

    def test_fail_still_blocks_alongside_warn(self):
        steps = [Step("token_bill", WARN), Step("x", "fail")]
        self.assertEqual(_overall(steps), "fail")


class ScriptJsonOutput(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _fixture(self) -> Path:
        path = self.root / "session.jsonl"
        rows = [
            {"type": "assistant", "requestId": "r1",
             "message": {"model": "m", "usage": {
                 "input_tokens": 100, "cache_creation_input_tokens": 1000,
                 "cache_read_input_tokens": 10000, "output_tokens": 200}, "content": []}},
            {"type": "assistant", "requestId": "r2",
             "message": {"model": "m", "usage": {
                 "input_tokens": 50, "cache_creation_input_tokens": 500,
                 "cache_read_input_tokens": 20000, "output_tokens": 100}, "content": []}},
        ]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def test_json_flag_emits_structured_bill(self):
        fixture = self._fixture()
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--json", str(fixture)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        stats = json.loads(result.stdout.strip())
        self.assertEqual(stats["api_calls"], 2)
        self.assertEqual(stats["cache_read_input_tokens"], 30000)
        # 150 + 1500*1.25 + 30000*0.1 + 300*5 = 6525
        self.assertEqual(stats["cost_weighted"], 6525)
        self.assertEqual(stats["context"]["max"], 20550)

    def test_text_output_unchanged_without_flag(self):
        fixture = self._fixture()
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), str(fixture)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cost-weighted units", result.stdout)
        self.assertIn("api_calls=2", result.stdout)


if __name__ == "__main__":
    unittest.main()