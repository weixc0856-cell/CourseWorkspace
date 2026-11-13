from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.platform.run_record import (
    finish_run,
    load_run,
    new_run,
    next_pending,
    run_path,
    save_run,
    update_stage,
)


class RunRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_new_run_writes_one_record_with_kernel_stages(self) -> None:
        record, path = new_run(self.workspace, "demo", "course")
        self.assertTrue(path.is_file())
        self.assertEqual(path, run_path(self.workspace, record.run_id))
        self.assertEqual(
            [stage.name for stage in record.stages],
            ["ingest", "understand", "plan", "author", "direct", "produce", "verify", "deliver"],
        )
        self.assertEqual(record.status, "running")

    def test_stage_transition_keeps_timestamps(self) -> None:
        record, path = new_run(self.workspace, "demo", "course")
        record = update_stage(record, "ingest", "pass", outputs=["knowledge/index.json"])
        save_run(record, run_path(self.workspace, record.run_id))
        saved = load_run(self.workspace, record.run_id)
        stage = next(item for item in saved.stages if item.name == "ingest")
        self.assertEqual(stage.status, "pass")
        self.assertEqual(stage.outputs, ["knowledge/index.json"])
        self.assertIsNotNone(stage.started_at)
        self.assertIsNotNone(stage.finished_at)
        self.assertEqual(next_pending(saved).name, "understand")

    def test_unknown_stage_is_rejected(self) -> None:
        record, _ = new_run(self.workspace, "demo", "course")
        with self.assertRaises(KeyError):
            update_stage(record, "publish", "pass")

    def test_finish_run_sets_status_and_time(self) -> None:
        record, _ = new_run(self.workspace, "demo", "course")
        record = finish_run(record, "completed")
        self.assertEqual(record.status, "completed")
        self.assertIsNotNone(record.finished_at)
