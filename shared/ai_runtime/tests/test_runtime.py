from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ai_runtime.budget import (
    ContextBudget,
    ContextOverflow,
    estimate_image_tokens,
    estimate_messages_tokens,
    estimate_text_tokens,
)
from ai_runtime.locks import FileLock, LockTimeout
from ai_runtime.tasks import TaskRecord, TaskStore


class TextBudgetTest(unittest.TestCase):
    def test_ascii_and_cjk(self):
        self.assertEqual(estimate_text_tokens(""), 0)
        self.assertEqual(estimate_text_tokens("abcd"), 1)
        self.assertEqual(estimate_text_tokens("字字字字"), 4)
        self.assertGreater(estimate_text_tokens("中文 mixed 文本"), 2)

    def test_messages(self):
        messages = [
            {"role": "system", "content": "abcd"},
            {"role": "user", "content": "字" * 10},
        ]
        self.assertGreaterEqual(estimate_messages_tokens(messages), 14)

    def test_image_estimate_uses_pixels_and_minimum(self):
        self.assertEqual(estimate_image_tokens(750, 1), 1)
        self.assertEqual(estimate_image_tokens(1280, 720), 1229)
        self.assertEqual(estimate_image_tokens(10, 10, min_tokens=1024), 1024)

    def test_overflow_raises_instead_of_truncating(self):
        budget = ContextBudget(limit=100, reserved_output=10)
        with self.assertRaises(ContextOverflow) as raised:
            budget.check([{"role": "user", "content": "字" * 200}])
        self.assertIn("split", str(raised.exception))

    def test_hard_ceiling(self):
        with self.assertRaises(ValueError):
            ContextBudget(limit=65537)

    def test_budget_report(self):
        budget = ContextBudget(limit=1000, reserved_output=100)
        report = budget.check([{"role": "user", "content": "abcd"}])
        self.assertTrue(report.ok)
        self.assertEqual(report.as_dict()["limit_tokens"], 1000)


class FileLockTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "locks" / "model.lock"

    def tearDown(self):
        self.temp.cleanup()

    def test_mutual_exclusion_and_release(self):
        first = FileLock(self.path, task_id="a", timeout_s=1)
        first.acquire()
        self.assertTrue(self.path.is_file())
        second = FileLock(self.path, task_id="b", timeout_s=0.3, poll_s=0.05)
        with self.assertRaises(LockTimeout):
            second.acquire()
        first.release()
        self.assertFalse(self.path.exists())
        second.acquire()
        second.release()

    def test_stale_lock_is_reclaimed(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "pid": 999999,
                    "task_id": "dead",
                    "host": "x",
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "acquired_at": time.time() - 10_000,
                }
            ),
            encoding="utf-8",
        )
        lock = FileLock(self.path, task_id="alive", timeout_s=1, poll_s=0.05)
        lock.acquire()
        self.assertEqual(lock.read().task_id, "alive")
        lock.release()

    def test_foreign_lock_is_not_released(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "task_id": "other",
                    "host": "x",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "acquired_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
        lock = FileLock(self.path, task_id="mine", timeout_s=0)
        lock._held = True
        lock.release()
        self.assertTrue(self.path.exists(), "foreign lock must survive")


class TaskStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_lifecycle_and_persistence(self):
        record = TaskRecord(
            task_id="t1",
            task_type="modeling.plan",
            assigned_model="m",
            status="pending",
        )
        saved = self.store.run(record, lambda: {"output_artifacts": ["model_plan.json"]})
        self.assertEqual(saved.status, "completed")
        loaded = self.store.load("t1")
        self.assertEqual(loaded.status, "completed")
        self.assertEqual(loaded.output_artifacts, ["model_plan.json"])
        self.assertIsNotNone(loaded.started_at)

    def test_failure_is_persisted_and_reraised(self):
        record = TaskRecord(task_id="t2", task_type="x", assigned_model="m")

        def boom():
            raise TimeoutError("model timed out")

        with self.assertRaises(TimeoutError):
            self.store.run(record, boom)
        loaded = self.store.load("t2")
        self.assertEqual(loaded.status, "failed")
        self.assertIn("model timed out", loaded.error)

    def test_invalid_record_rejected(self):
        with self.assertRaises(ValueError):
            TaskRecord.from_dict({"schema_version": 1, "task_id": "x"})
        with self.assertRaises(ValueError):
            TaskRecord(task_id="x", task_type="y", assigned_model="m", status="done")


class SchemaFileTest(unittest.TestCase):
    def test_committed_task_schema_matches(self):
        workspace = Path(__file__).resolve().parents[3]
        import json as _json
        from ai_runtime.tasks import schema

        committed = (workspace / "shared" / "schemas" / "model-task.schema.json").read_text(encoding="utf-8").rstrip("\n")
        rendered = _json.dumps(schema(), ensure_ascii=False, indent=2)
        self.assertEqual(rendered, committed)


if __name__ == "__main__":
    unittest.main()
