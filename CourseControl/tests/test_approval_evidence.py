"""Approval provenance gate (E2): tool marker + placeholder timestamps.

Negative examples prove the audit can go red on hand-written entries; the
positive path proves CLI approvals stay green. assert_approved's hash/name
gate is intentionally untouched (in-flight production must not stall).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from course_control.authoring.pipeline import (
    APPROVAL_TOOL,
    approval_evidence_problems,
    approve,
    apply_acceptance,
    load_approval,
    plan_acceptance,
)

WORKSPACE = Path(__file__).resolve().parents[2]
SHA = "a" * 64


def _entry(path: str, approved_at: str, tool: str | None = None) -> dict:
    entry = {
        "kind": "content",
        "path": path,
        "sha256": SHA,
        "approved_by": "Wayne",
        "approved_at": approved_at,
    }
    if tool is not None:
        entry["tool"] = tool
    return entry


class ApprovalEvidenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lesson = Path(self._tmp.name) / "demo-lesson"
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "slides.md").write_text("# demo\n", encoding="utf-8")

    def _write_approval(self, entries: list[dict]) -> None:
        (self.lesson / "authoring" / "approval.json").write_text(
            json.dumps(
                {"schema_version": 1, "lesson": "demo-lesson", "approvals": entries}
            ),
            encoding="utf-8",
        )

    def test_handwritten_placeholder_entry_is_flagged(self):
        # Negative 1: the exact T1-01 pattern — no tool, midnight UTC.
        self._write_approval([_entry("slides.md", "2026-11-21T00:00:00Z")])
        problems = approval_evidence_problems(self.lesson)
        self.assertTrue(any("no tool provenance" in p for p in problems), problems)
        self.assertTrue(any("placeholder timestamp" in p for p in problems), problems)

    def test_missing_tool_marker_is_flagged(self):
        # Negative 2: a plausible timestamp still lacks provenance.
        self._write_approval(
            [_entry("slides.md", "2026-11-21T11:31:05+08:00")]
        )
        problems = approval_evidence_problems(self.lesson)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no tool provenance", problems[0])

    def test_unparseable_timestamp_is_flagged(self):
        self._write_approval(
            [_entry("slides.md", "yesterday", tool=APPROVAL_TOOL)]
        )
        problems = approval_evidence_problems(self.lesson)
        self.assertTrue(any("placeholder timestamp" in p for p in problems), problems)

    def test_approve_writes_provenance_and_passes(self):
        entry = approve(self.lesson, "content", "slides.md", "Wayne")
        self.assertEqual(entry.tool, APPROVAL_TOOL)
        stored = load_approval(self.lesson).find("slides.md")
        self.assertEqual(stored.tool, APPROVAL_TOOL)
        self.assertEqual(approval_evidence_problems(self.lesson), [])

    def test_superseded_placeholder_is_history(self):
        self._write_approval([_entry("slides.md", "2026-11-21T00:00:00Z")])
        approve(self.lesson, "content", "slides.md", "Wayne")
        self.assertEqual(approval_evidence_problems(self.lesson), [])

    def test_local_midnight_with_tool_is_not_flagged(self):
        # A genuine local-midnight approval carries an offset, not UTC.
        self._write_approval(
            [_entry("slides.md", "2026-11-21T00:00:00+08:00", tool=APPROVAL_TOOL)]
        )
        self.assertEqual(approval_evidence_problems(self.lesson), [])

    def test_no_approval_file_is_not_a_problem_here(self):
        self.assertEqual(approval_evidence_problems(self.lesson), [])

    def test_production_kind_plans_and_approves(self):
        workspace = Path(self._tmp.name)
        (self.lesson / "authoring" / "production.yaml").write_text(
            "schema_version: 1\n", encoding="utf-8"
        )
        plans = plan_acceptance(
            workspace, self.lesson, "production", source="current"
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].action, "approve-current")
        self.assertEqual(plans[0].relative, "authoring/production.yaml")
        apply_acceptance(
            workspace, self.lesson, "production", "Wayne", source="current",
            dry_run=True,
        )
        self.assertFalse((self.lesson / "authoring" / "approval.json").exists())
        apply_acceptance(
            workspace, self.lesson, "production", "Wayne", source="current"
        )
        entry = load_approval(self.lesson).find("authoring/production.yaml")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.kind, "production")
        self.assertEqual(entry.tool, APPROVAL_TOOL)
        self.assertEqual(approval_evidence_problems(self.lesson), [])


class ContentAuditProvenanceTest(unittest.TestCase):
    """The production content audit surfaces provenance warnings; --strict
    (the release gate) turns them into failures."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "lessons").mkdir()
        (self.root / "build" / "_shared").mkdir(parents=True)
        (self.root / "deliver").mkdir()
        self._env = mock.patch.dict(
            os.environ,
            {"COURSEWORKSPACE_MODE": "", "COURSEWORKSPACE_CONTENT_ROOT": str(self.root)},
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        lesson = self.root / "lessons" / "demo"
        lesson.mkdir()
        (lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ntitle_en: Demo\ntitle_zh: 演示\n"
            "status: draft\n"
            "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
            "  storyboard: storyboard.yaml\n  assets: assets/\n"
            "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
            "  slides_canvas: [1280, 720]\n  animation_canvas: [1920, 1080]\n"
            "engines: [manim]\ncompose:\n  mode: deck\n",
            encoding="utf-8",
        )
        for name in ("slides.md", "lecture_notes.md"):
            (lesson / name).write_text("demo\n", encoding="utf-8")
        (lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\n", encoding="utf-8"
        )
        (lesson / "authoring").mkdir()
        (lesson / "authoring" / "approval.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "lesson": "demo",
                    "approvals": [_entry("slides.md", "2026-11-21T00:00:00Z")],
                }
            ),
            encoding="utf-8",
        )

    def test_placeholder_approval_warns_and_strict_fails(self):
        from course_control.platform.content_audit import run_audit

        result = run_audit(WORKSPACE)
        warnings = [item for item in result.warnings if item.area == "lessons"]
        self.assertTrue(
            any("placeholder timestamp" in item.detail for item in warnings),
            [item.detail for item in result.findings],
        )
        self.assertFalse(result.errors)
        self.assertEqual(result.status(), "incomplete")
        strict = run_audit(WORKSPACE, strict=True)
        self.assertEqual(strict.status(strict=True), "fail")

    def test_cli_approval_keeps_audit_green(self):
        from course_control.platform.content_audit import run_audit

        lesson = self.root / "lessons" / "demo"
        approve(lesson, "content", "slides.md", "Wayne")
        result = run_audit(WORKSPACE)
        self.assertFalse(
            [item for item in result.warnings if "provenance" in item.detail
             or "placeholder" in item.detail],
            [item.detail for item in result.findings],
        )
        self.assertFalse(result.errors)


if __name__ == "__main__":
    unittest.main()