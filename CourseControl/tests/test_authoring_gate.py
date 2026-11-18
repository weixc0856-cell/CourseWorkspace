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


class CandidateSafetyTest(unittest.TestCase):
    """A candidate may only replace the file it was generated against.

    The failure this pins: an old draft silently overwrote a hand-edited
    script, so the lesson went back to 54 segments after the owner had grown it
    to 68.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path as PathType

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = PathType(self._tmp.name)
        self.lesson = self.workspace / "lessons" / "demo"
        (self.lesson / "authoring").mkdir(parents=True)
        self.candidates = (
            self.workspace / "build" / "demo" / "authoring" / "candidates"
        )
        self.candidates.mkdir(parents=True)
        self.target = self.lesson / "authoring" / "narration.script.json"
        self.target.write_text('{"segments": 68}\n', encoding="utf-8")
        (self.lesson / "authoring" / "narration.script.md").write_text(
            "segments: 68\n", encoding="utf-8"
        )
        self.candidate = self.candidates / "narration.script.json"
        self.candidate.write_text('{"segments": 54}\n', encoding="utf-8")
        (self.candidates / "narration.script.md").write_text(
            "segments: 54\n", encoding="utf-8"
        )

    def _record(self, target_sha: str | None = None) -> None:
        import json

        files = {}
        for name in ("narration.script.json", "narration.script.md"):
            relative = f"authoring/{name}"
            target = self.lesson / relative
            files[name] = {
                "candidate": name,
                "target": relative,
                "candidate_sha256": "0" * 64,
                "target_sha256": (
                    target_sha
                    if target_sha is not None
                    else (self._sha(target) if target.is_file() else None)
                ),
                "generated_at": "2026-11-18T00:00:00+08:00",
            }
        (self.candidates / "candidates.json").write_text(
            json.dumps(
                {"schema_version": 1, "lesson": "demo", "files": files}
            ),
            encoding="utf-8",
        )

    def _sha(self, path: Path) -> str:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_stale_candidate_is_refused(self):
        from course_control.authoring.pipeline import apply_acceptance

        self._record(target_sha="f" * 64)
        with self.assertRaisesRegex(Exception, "changed after this candidate"):
            apply_acceptance(
                self.workspace,
                self.lesson,
                "script",
                "Wei Chen",
            )
        self.assertEqual(
            self.target.read_text(encoding="utf-8"), '{"segments": 68}\n'
        )
        self.assertEqual(
            (self.lesson / "authoring" / "narration.script.md").read_text(
                encoding="utf-8"
            ),
            "segments: 68\n",
        )

    def test_force_replace_promotes_the_candidate(self):
        from course_control.authoring.pipeline import apply_acceptance

        self._record(target_sha="f" * 64)
        apply_acceptance(
            self.workspace,
            self.lesson,
            "script",
            "Wei Chen",
            force_replace=True,
        )
        self.assertEqual(
            self.target.read_text(encoding="utf-8"), '{"segments": 54}\n'
        )
        self.assertEqual(
            (self.lesson / "authoring" / "narration.script.md").read_text(
                encoding="utf-8"
            ),
            "segments: 54\n",
        )

    def test_candidate_without_record_is_refused(self):
        from course_control.authoring.pipeline import apply_acceptance

        with self.assertRaisesRegex(Exception, "no generation record"):
            apply_acceptance(self.workspace, self.lesson, "script", "Wei Chen")

    def test_current_source_approves_without_rewriting(self):
        from course_control.authoring.pipeline import (
            apply_acceptance,
            assert_approved,
        )

        before = self.target.read_bytes()
        plans = apply_acceptance(
            self.workspace,
            self.lesson,
            "script",
            "Wei Chen",
            source="current",
            expect_sha256=self._sha(self.target),
        )
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].action, "approve-current")
        self.assertEqual(self.target.read_bytes(), before)
        assert_approved(self.lesson, "authoring/narration.script.json")

    def test_expect_sha_mismatch_is_refused(self):
        from course_control.authoring.pipeline import apply_acceptance

        with self.assertRaisesRegex(Exception, "not"):
            apply_acceptance(
                self.workspace,
                self.lesson,
                "script",
                "Wei Chen",
                source="current",
                expect_sha256="0" * 64,
            )

    def test_dry_run_writes_nothing(self):
        from course_control.authoring.pipeline import apply_acceptance

        self._record()
        before = self.target.read_bytes()
        plans = apply_acceptance(
            self.workspace,
            self.lesson,
            "script",
            "Wei Chen",
            dry_run=True,
        )
        self.assertEqual(plans[0].action, "replace")
        self.assertTrue(plans[0].diff.startswith("+1/-1"))
        self.assertEqual(self.target.read_bytes(), before)
        self.assertFalse((self.lesson / "authoring" / "approval.json").exists())


if __name__ == "__main__":
    unittest.main()
