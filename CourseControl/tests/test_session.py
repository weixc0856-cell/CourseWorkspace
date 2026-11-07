from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_control.session import (
    SessionContractError,
    cache_key,
    load_session_spec,
    normalize_stream,
    sha256_text,
)
from course_control.session_runner import SessionRunError, run_session

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON_DIR = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"
SPEC = LESSON_DIR / "sessions" / "shell-001.session.json"


class SessionContractTest(unittest.TestCase):
    def test_fixture_passes(self):
        spec = load_session_spec(SPEC)
        self.assertEqual(spec.shot_id, "shell_001")
        self.assertEqual(spec.environment.network, "none")
        self.assertEqual(spec.commands[0].expect.stdout, "expected.txt")

    def test_vscode_session_spec_validates(self):
        spec = load_session_spec(LESSON_DIR / "sessions" / "vscode-001.session.json")
        self.assertEqual(spec.environment.kind, "host")
        self.assertIsNone(spec.environment.image)
        self.assertEqual(spec.record.target, "vscode")

    def test_rust_session_spec_validates(self):
        spec = load_session_spec(LESSON_DIR / "sessions" / "rust-001.session.json")
        self.assertEqual(spec.environment.kind, "host")
        self.assertEqual(spec.record.target, "vscode")

    def test_python_network_session_spec_validates(self):
        spec = load_session_spec(
            LESSON_DIR / "sessions" / "python-network-001.session.json"
        )
        self.assertEqual(spec.environment.network, "bridge")
        self.assertEqual(len(spec.offline_commands), 1)

    def test_python_offline_session_spec_validates(self):
        spec = load_session_spec(LESSON_DIR / "sessions" / "python-001.session.json")
        self.assertEqual(spec.environment.network, "bridge")
        self.assertEqual(len(spec.offline_commands), 1)
        self.assertEqual(spec.offline_commands[0].id, "o1")

    def test_duplicate_command_rejected(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["commands"].append(dict(data["commands"][0]))
        with self.assertRaises(ValidationError):
            from course_control.session import SessionSpec

            SessionSpec.model_validate(data)

    def test_trim_must_reference_command(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["commands"][0]["trim"] = {"command": "missing"}
        with self.assertRaises(ValidationError):
            from course_control.session import SessionSpec

            SessionSpec.model_validate(data)

    def test_absolute_file_path_rejected(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["files"][0]["path"] = "/abs/hello.sh"
        with self.assertRaises(ValidationError):
            from course_control.session import SessionSpec

            SessionSpec.model_validate(data)

    def test_normalize_stream(self):
        self.assertEqual(
            normalize_stream("\x1b[31mred\x1b[0m  \r\nhello\r\n\r\n"),
            "red\nhello",
        )

    def test_cache_key_changes_with_files(self):
        spec = load_session_spec(SPEC)
        first = cache_key(spec, {"hello.sh": sha256_text("a")}, "sha256:1")
        second = cache_key(spec, {"hello.sh": sha256_text("b")}, "sha256:1")
        third = cache_key(spec, {"hello.sh": sha256_text("a")}, "sha256:2")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, third)


def _docker_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@unittest.skipUnless(
    os.environ.get("COURSE_SESSION_INTEGRATION") == "1" and _docker_available(),
    "set COURSE_SESSION_INTEGRATION=1 and start Docker to run",
)
class SessionIntegrationTest(unittest.TestCase):
    def test_headless_session_passes(self):
        result, manifest, recording = run_session(
            WORKSPACE, SPEC, LESSON_DIR, record=False
        )
        self.assertEqual(result.status, "passed")
        self.assertIsNone(result.failure)
        self.assertIsNone(recording)
        self.assertEqual(manifest.execution_result, "result.json")
        self.assertTrue((WORKSPACE / "build" / "lesson-smoke" / "code" / "shell_001" / "result.json").is_file())

    def test_wrong_expected_output_fails(self):
        data = json.loads(SPEC.read_text(encoding="utf-8"))
        data["commands"][0]["expect"] = {"exit_code": 1}
        data["commands"][0]["run"] = ["bash", "-lc", "printf 'wrong\\n'"]
        data["files"] = []
        temp = LESSON_DIR / "sessions" / "wrong.session.json"
        temp.write_text(json.dumps(data), encoding="utf-8")
        try:
            result, _manifest, _recording = run_session(
                WORKSPACE, temp, LESSON_DIR, record=False
            )
            self.assertEqual(result.status, "failed")
            self.assertIn(result.failure.value, {"execution_failed", "assertion_failed"})
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
