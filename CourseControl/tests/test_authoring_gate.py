from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.authoring.pipeline import (
    approve,
    assert_approved,
    load_approval,
)


class ApprovalGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lesson = Path(self._tmp.name) / "lessons" / "test-lesson"
        (self.lesson / "authoring").mkdir(parents=True)
        self.target = self.lesson / "authoring" / "narration.script.json"
        self.target.write_text('{"schema_version": 1}\n', encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_approve_then_verify(self):
        entry = approve(self.lesson, "script", "authoring/narration.script.json")
        self.assertEqual(len(entry.sha256), 64)
        assert_approved(self.lesson, "authoring/narration.script.json")
        approval = load_approval(self.lesson)
        self.assertIsNotNone(approval.find("authoring/narration.script.json"))

    def test_change_after_approval_is_rejected(self):
        approve(self.lesson, "script", "authoring/narration.script.json")
        self.target.write_text('{"schema_version": 1, "changed": true}\n', encoding="utf-8")
        with self.assertRaises(Exception):
            assert_approved(self.lesson, "authoring/narration.script.json")

    def test_unapproved_file_is_rejected(self):
        with self.assertRaises(Exception):
            assert_approved(self.lesson, "authoring/narration.script.json")

    def test_approve_missing_file_is_rejected(self):
        with self.assertRaises(Exception):
            approve(self.lesson, "script", "authoring/missing.json")


if __name__ == "__main__":
    unittest.main()
