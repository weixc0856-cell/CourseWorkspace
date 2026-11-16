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
        entry = approve(self.lesson, "script", "authoring/narration.script.json", "Wei Chen")
        self.assertEqual(len(entry.sha256), 64)
        assert_approved(self.lesson, "authoring/narration.script.json")
        approval = load_approval(self.lesson)
        self.assertIsNotNone(approval.find("authoring/narration.script.json"))

    def test_change_after_approval_is_rejected(self):
        approve(self.lesson, "script", "authoring/narration.script.json", "Wei Chen")
        self.target.write_text('{"schema_version": 1, "changed": true}\n', encoding="utf-8")
        with self.assertRaises(Exception):
            assert_approved(self.lesson, "authoring/narration.script.json")

    def test_unapproved_file_is_rejected(self):
        with self.assertRaises(Exception):
            assert_approved(self.lesson, "authoring/narration.script.json")

    def test_bad_approver_does_not_replace_content(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from course_control.authoring.pipeline import accept_content

        with tempfile.TemporaryDirectory() as tmp:
            workspace = _Path(tmp)
            lesson = workspace / "lessons" / "demo"
            (lesson / "assets").mkdir(parents=True)
            for name in ("slides.md", "lecture_notes.md", "storyboard.yaml"):
                (lesson / name).write_text(f"original {name}", encoding="utf-8")
            candidates = workspace / "build" / "demo" / "authoring" / "candidates"
            candidates.mkdir(parents=True)
            for name in ("slides.md", "lecture_notes.md", "storyboard.yaml"):
                (candidates / name).write_text(f"candidate {name}", encoding="utf-8")
            with self.assertRaises(Exception):
                accept_content(workspace, lesson, "human")
            for name in ("slides.md", "lecture_notes.md", "storyboard.yaml"):
                self.assertEqual(
                    (lesson / name).read_text(encoding="utf-8"), f"original {name}"
                )

    def test_old_machine_approval_is_rejected_on_read(self) -> None:
        import hashlib
        import json

        payload = {
            "schema_version": 1,
            "lesson": self.lesson.name,
            "approvals": [
                {
                    "kind": "script",
                    "path": "authoring/narration.script.json",
                    "sha256": hashlib.sha256(self.target.read_bytes()).hexdigest(),
                    "approved_by": "human",
                    "approved_at": "2026-11-15T10:00:00+00:00",
                }
            ],
        }
        (self.lesson / "authoring" / "approval.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with self.assertRaises(Exception):
            assert_approved(self.lesson, "authoring/narration.script.json")

    def test_machine_signature_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            approve(self.lesson, "script", "authoring/narration.script.json", "human")

    def test_approve_missing_file_is_rejected(self):
        with self.assertRaises(Exception):
            approve(self.lesson, "script", "authoring/missing.json", "Wei Chen")


if __name__ == "__main__":
    unittest.main()
