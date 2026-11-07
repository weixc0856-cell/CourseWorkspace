from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from course_control.session import EvidenceManifest, SessionSpec
from course_control.session_evidence_v1 import V1EvidenceError, adapt_session_evidence


class SessionEvidenceV1Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.lesson_dir = self.workspace / "lessons" / "lesson-x"
        self.build = self.workspace / "build" / "lesson-x" / "code" / "shell_001"
        self.spec_path = self.lesson_dir / "sessions" / "shell-001.session.json"
        self.spec = SessionSpec(
            schema_version=1,
            lesson="lesson-x",
            shot_id="shell_001",
            session_id="session-x-001",
            environment={"kind": "host"},
            files=[],
            commands=[{"id": "c1", "run": ["echo", "hello"]}],
        )
        self.spec_path.parent.mkdir(parents=True, exist_ok=True)
        self.spec_path.write_text(self.spec.model_dump_json(indent=2), encoding="utf-8")
        self.build.mkdir(parents=True, exist_ok=True)
        for name in ("result.json", "recording.json", "validation.json", "session.mp4"):
            (self.build / name).write_text("{}" if name.endswith(".json") else "x", encoding="utf-8")
        (self.build / "work").mkdir()
        (self.build / "work" / "transcript.log").write_text("hello\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write_evidence(self, recording: str | None) -> None:
        manifest = EvidenceManifest(
            shot_id="shell_001",
            session_id="session-x-001",
            spec_sha256="0" * 64,
            execution_result="result.json",
            recording_result=recording,
            validation_report="validation.json",
            transcript="work/transcript.log",
            artifacts=["session.mp4"],
            cache_key="cache-key",
        )
        (self.build / "evidence.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )

    def test_adapts_complete_evidence(self):
        self._write_evidence("recording.json")
        manifest = adapt_session_evidence(
            self.spec_path,
            self.workspace,
            run_id="20261107T140000Z-deadbeef",
            now=datetime(2026, 11, 7, 14, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(manifest.kind, "evidence_manifest")
        self.assertEqual(manifest.lesson_id, "lesson-x")
        self.assertEqual(manifest.shot_id, "shell_001")
        self.assertEqual(manifest.run_id, "20261107T140000Z-deadbeef")
        self.assertEqual(manifest.execution_result.path, "build/lesson-x/code/shell_001/result.json")
        self.assertEqual(manifest.recording_result.path, "build/lesson-x/code/shell_001/recording.json")
        self.assertEqual(manifest.transcript.path, "build/lesson-x/code/shell_001/work/transcript.log")
        self.assertEqual(len(manifest.artifacts), 1)
        self.assertFalse(manifest.legacy["recording_result_inferred"])

    def test_infers_present_recording_and_flags_it(self):
        self._write_evidence(None)
        manifest = adapt_session_evidence(
            self.spec_path,
            self.workspace,
            run_id="20261107T140000Z-deadbeef",
        )
        self.assertTrue(manifest.legacy["recording_result_inferred"])

    def test_missing_recording_is_not_faked(self):
        self._write_evidence(None)
        (self.build / "recording.json").unlink()
        with self.assertRaises(V1EvidenceError):
            adapt_session_evidence(
                self.spec_path,
                self.workspace,
                run_id="20261107T140000Z-deadbeef",
            )


if __name__ == "__main__":
    unittest.main()
