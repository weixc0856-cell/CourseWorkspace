"""Tests for the independent review runner. No external tokens are consumed."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from review_runner.budget import BudgetPolicy
from review_runner.executor import (
    CodexSettings,
    ExecutorError,
    FakeCodexExecutor,
    ProviderInfo,
    build_argv,
    run_process,
)
from review_runner.parser import FindingsParseError, extract_findings, parse_events
from review_runner.runner import RunOptions, run_review
from review_runner.scope import deny_reason
from review_runner.schema import (
    ExecutionStatus,
    ReviewStatus,
    ReviewType,
)

PROVIDER = ProviderInfo(
    provider="deepseek",
    model="deepseek-flash",
    endpoint_host="api.deepseek.com",
    isolation="isolated",
    base_url="https://api.deepseek.com/v1",
)


def jsonl(
    message: str | None,
    *,
    input_tokens: int | None = 20000,
    output_tokens: int | None = 400,
    turn_completed: bool = True,
    extra: list[dict] | None = None,
) -> str:
    events: list[dict] = [
        {"type": "thread.started", "thread_id": "thread-test"},
        {"type": "turn.started"},
    ]
    events.extend(extra or [])
    if message is not None:
        events.append(
            {
                "type": "item.completed",
                "item": {"id": "i1", "type": "agent_message", "text": message},
            }
        )
    if turn_completed:
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            }
        )
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n"


def findings_message(findings: list[dict] | None = None) -> str:
    payload = {"findings": findings or []}
    return (
        "# Review Report\n\n本次审核完成。\n\n```json:findings\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
    )


def sample_finding(**overrides) -> dict:
    finding = {
        "severity": "P2",
        "category": "Correctness",
        "file": "a.py",
        "line": 2,
        "problem": "value is never used",
        "evidence": "a.py:2 assigns value and it is not read",
        "impact": "dead code hides a real branch",
        "suggested_fix": "remove the assignment or use it",
        "confidence": "high",
        "verification": "verified",
    }
    finding.update(overrides)
    return finding


class GitCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "review@test.local")
        self.git("config", "user.name", "Review Test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.output = self.repo / "build" / "reviews"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def write(self, relpath: str, text: str) -> Path:
        path = self.repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, message: str = "commit") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.head()

    def head(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def options(self, **overrides) -> RunOptions:
        values = dict(
            review_type=ReviewType.code,
            workspace=self.repo,
            output_root=self.output,
            provider_override=PROVIDER,
        )
        values.update(overrides)
        return RunOptions(**values)


class CodeReviewTests(GitCase):
    def test_commit_review_completes_and_archives(self) -> None:
        self.write("a.py", "def value():\n    return 1\n")
        self.commit("base")
        self.write("a.py", "def value():\n    unused = 1\n    return 2\n")
        sha = self.commit("change")

        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message([sample_finding()]))
        )
        outcome = run_review(self.options(commit=sha), executor=executor)

        self.assertEqual(outcome.exit_code, 0)
        manifest = outcome.manifest
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.execution_status, ExecutionStatus.success)
        self.assertEqual(manifest.review_status, ReviewStatus.completed)
        self.assertEqual(manifest.findings_count, 1)
        self.assertEqual(manifest.scope.commit, sha)
        self.assertEqual(manifest.scope.head_sha, self.head())
        self.assertFalse(manifest.scope.worktree_dirty)
        self.assertEqual(manifest.privacy.granted, True)
        self.assertEqual(manifest.production_effect, "none")

        review_dir = outcome.review_dir
        assert review_dir is not None
        for name in (
            "manifest.json",
            "input-files.txt",
            "events.jsonl",
            "review.md",
            "execution.log",
            "findings.json",
            "input.sha256",
            "input/diff.patch",
            "input/REVIEW_TASK.md",
            "input/a.py",
        ):
            self.assertTrue((review_dir / name).is_file(), name)

        findings = json.loads((review_dir / "findings.json").read_text("utf-8"))
        self.assertEqual(findings["findings"][0]["verification"], "unverified")
        self.assertEqual(findings["production_effect"], "none")

        # The snapshot is the committed blob, byte for byte.
        snapshot_text = (review_dir / "input" / "a.py").read_text("utf-8")
        self.assertIn("unused = 1", snapshot_text)
        self.assertIn("diff.patch", (review_dir / "input-files.txt").read_text("utf-8"))

    def test_unknown_commit_is_a_contract_error(self) -> None:
        self.write("a.py", "x = 1\n")
        self.commit()
        outcome = run_review(self.options(commit="does-not-exist"))
        self.assertEqual(outcome.exit_code, 1)
        self.assertIsNone(outcome.review_dir)

    def test_dirty_worktree_is_recorded_not_used(self) -> None:
        self.write("a.py", "committed = True\n")
        sha = self.commit()
        self.write("a.py", "dirty = True\n")

        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(self.options(commit=sha), executor=executor)

        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None and outcome.review_dir is not None
        self.assertTrue(outcome.manifest.scope.worktree_dirty)
        snapshot = (outcome.review_dir / "input" / "a.py").read_text("utf-8")
        self.assertIn("committed = True", snapshot)
        self.assertNotIn("dirty = True", snapshot)

    def test_scope_rejects_path_traversal_context(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(
            self.options(commit=sha, context_files=("../outside.txt",)),
            executor=executor,
        )
        self.assertEqual(outcome.exit_code, 1)
        assert outcome.manifest is not None
        self.assertIn("SCOPE_REJECTED", outcome.manifest.flags)
        self.assertEqual(executor.calls, [])

    def test_budget_guard_blocks_without_execution(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        policy = BudgetPolicy(system_reserve=100000)
        outcome = run_review(
            self.options(commit=sha), executor=executor, policy=policy
        )
        self.assertEqual(outcome.exit_code, 2)
        assert outcome.manifest is not None
        self.assertIn("BUDGET_BLOCKED", outcome.manifest.flags)
        self.assertEqual(executor.calls, [])

    def test_sensitive_files_are_excluded_from_snapshot(self) -> None:
        self.write("a.py", "x = 1\n")
        self.write(".env", "SECRET_TOKEN=do-not-send\n")
        self.write("config/local-paths.yaml", "root: D:/private\n")
        self.git("add", "-f", ".env", "config/local-paths.yaml")
        sha = self.commit()

        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(self.options(commit=sha), executor=executor)

        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None and outcome.review_dir is not None
        excluded = {item.path for item in outcome.manifest.exclusions}
        self.assertIn(".env", excluded)
        self.assertIn("config/local-paths.yaml", excluded)
        diff = (outcome.review_dir / "input" / "diff.patch").read_text("utf-8")
        self.assertNotIn("do-not-send", diff)
        self.assertFalse((outcome.review_dir / "input" / ".env").exists())
        self.assertFalse(
            (outcome.review_dir / "input" / "config" / "local-paths.yaml").exists()
        )

    def test_snapshot_mutation_is_detected(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()

        def mutate(cwd: Path) -> None:
            (cwd / "a.py").write_text("mutated\n", encoding="utf-8")

        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message()), on_run=mutate
        )
        outcome = run_review(self.options(commit=sha), executor=executor)

        self.assertEqual(outcome.exit_code, 3)
        assert outcome.manifest is not None
        self.assertEqual(outcome.manifest.execution_status, ExecutionStatus.failed)
        self.assertFalse(outcome.manifest.execution.snapshot_intact)
        self.assertIn("SNAPSHOT_MUTATED", outcome.manifest.flags)

    def test_repeat_review_uses_distinct_directories(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        first = run_review(
            self.options(commit=sha),
            executor=FakeCodexExecutor(stdout=jsonl(findings_message())),
        )
        second = run_review(
            self.options(commit=sha),
            executor=FakeCodexExecutor(stdout=jsonl(findings_message())),
        )
        self.assertNotEqual(first.review_dir, second.review_dir)
        self.assertTrue(first.review_dir is not None and first.review_dir.is_dir())
        self.assertTrue(second.review_dir is not None and second.review_dir.is_dir())

    def test_base_review_uses_merge_base_range(self) -> None:
        self.write("a.py", "base\n")
        self.commit("base")
        self.git("branch", "main")
        self.write("a.py", "feature\n")
        self.write("b.py", "new\n")
        self.commit("feature")

        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(self.options(base="main"), executor=executor)

        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None and outcome.review_dir is not None
        self.assertEqual(outcome.manifest.scope.base, "main")
        self.assertEqual(outcome.manifest.scope.review_rev, self.head())
        reviewed = {record.path for record in outcome.manifest.files}
        self.assertIn("b.py", reviewed)

    def test_dry_run_prepares_snapshot_without_execution(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(
            self.options(commit=sha, dry_run=True), executor=executor
        )
        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None and outcome.review_dir is not None
        self.assertIn("DRY_RUN", outcome.manifest.flags)
        self.assertEqual(outcome.manifest.execution_status, ExecutionStatus.not_run)
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.not_run)
        self.assertEqual(executor.calls, [])
        self.assertTrue((outcome.review_dir / "input" / "a.py").is_file())

    def test_code_review_rejects_files_option(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        outcome = run_review(self.options(commit=sha, files=("a.py",)))
        self.assertEqual(outcome.exit_code, 1)
        self.assertIsNone(outcome.review_dir)


class PrivacyAndTypeTests(GitCase):
    def test_course_review_requires_explicit_grant(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(
            self.options(review_type=ReviewType.course, commit=sha),
            executor=executor,
        )
        self.assertEqual(outcome.exit_code, 2)
        assert outcome.manifest is not None
        self.assertIn("PRIVACY_BLOCKED", outcome.manifest.flags)
        self.assertEqual(executor.calls, [])

    def test_course_review_grant_passes_privacy_but_is_not_implemented(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(
            self.options(
                review_type=ReviewType.course,
                commit=sha,
                allow_external_content=True,
            ),
            executor=executor,
        )
        self.assertEqual(outcome.exit_code, 1)
        assert outcome.manifest is not None
        self.assertIn("NOT_IMPLEMENTED", outcome.manifest.flags)
        self.assertTrue(outcome.manifest.privacy.granted)
        self.assertEqual(executor.calls, [])

    def test_docs_review_requires_explicit_files(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(stdout=jsonl(findings_message()))
        outcome = run_review(
            self.options(review_type=ReviewType.docs, commit=sha),
            executor=executor,
        )
        self.assertEqual(outcome.exit_code, 2)
        assert outcome.manifest is not None
        self.assertIn("PRIVACY_BLOCKED", outcome.manifest.flags)
        self.assertEqual(executor.calls, [])


class ExecutionFailureTests(GitCase):
    def test_nonzero_exit_marks_execution_failed(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(
            stdout="", stderr="boom\n", exit_code=2
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 3)
        assert outcome.manifest is not None
        self.assertEqual(outcome.manifest.execution_status, ExecutionStatus.failed)
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.not_run)

    def test_incomplete_jsonl_marks_review_incomplete(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message(), turn_completed=False)
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 3)
        assert outcome.manifest is not None
        self.assertEqual(outcome.manifest.execution_status, ExecutionStatus.success)
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.incomplete)

    def test_invalid_findings_keep_raw_message(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(
            stdout=jsonl("# Review Report\n\nno findings block\n")
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 3)
        assert outcome.manifest is not None and outcome.review_dir is not None
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.incomplete)
        self.assertIsNone(outcome.manifest.findings_count)
        self.assertTrue((outcome.review_dir / "review.md").is_file())
        self.assertFalse((outcome.review_dir / "findings.json").exists())

    def test_noise_is_filtered_not_treated_as_error(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        noise = [
            {
                "type": "item.completed",
                "item": {
                    "id": "e1",
                    "type": "error",
                    "message": "failed to load skill C:\\x\\SKILL.md: missing YAML frontmatter",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "e2",
                    "type": "error",
                    "message": "Model metadata for `x` not found. Defaulting to fallback metadata",
                },
            },
        ]
        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message(), extra=noise)
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None
        self.assertEqual(outcome.manifest.execution.noise_filtered, 2)
        self.assertEqual(outcome.manifest.execution.errors, [])

    def test_budget_violation_prevents_completed_review(self) -> None:
        self.write("a.py", "x = 1\n")
        sha = self.commit()
        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message(), input_tokens=70000, output_tokens=1000)
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 3)
        assert outcome.manifest is not None
        self.assertIn("BUDGET_VIOLATION", outcome.manifest.flags)
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.incomplete)

    def test_large_output_is_a_warning_not_a_violation(self) -> None:
        self.write("a.py", "x = 1")
        sha = self.commit()
        executor = FakeCodexExecutor(
            stdout=jsonl(findings_message(), input_tokens=49976, output_tokens=61814)
        )
        outcome = run_review(self.options(commit=sha), executor=executor)
        self.assertEqual(outcome.exit_code, 0)
        assert outcome.manifest is not None
        self.assertNotIn("BUDGET_VIOLATION", outcome.manifest.flags)
        self.assertIn("OUTPUT_OVER_RESERVE", outcome.manifest.flags)
        self.assertEqual(outcome.manifest.review_status, ReviewStatus.completed)


class ParserTests(unittest.TestCase):
    def test_parse_usage_thread_and_last_message(self) -> None:
        text = jsonl("first") + jsonl("second")
        parsed = parse_events(text)
        self.assertEqual(parsed.thread_id, "thread-test")
        self.assertEqual(parsed.last_agent_message, "second")
        self.assertEqual(parsed.usage["input_tokens"], 20000)
        self.assertTrue(parsed.jsonl_complete)

    def test_invalid_line_breaks_completeness(self) -> None:
        parsed = parse_events("not json\n" + jsonl(findings_message()))
        self.assertFalse(parsed.jsonl_complete)
        self.assertEqual(len(parsed.invalid_lines), 1)

    def test_findings_are_forced_unverified(self) -> None:
        envelope = extract_findings(findings_message([sample_finding()]))
        self.assertEqual(len(envelope.findings), 1)
        self.assertEqual(envelope.findings[0].verification.value, "unverified")

    def test_invalid_severity_is_rejected(self) -> None:
        with self.assertRaises(FindingsParseError):
            extract_findings(
                findings_message([sample_finding(severity="BLOCKER")])
            )

    def test_missing_fence_is_rejected(self) -> None:
        with self.assertRaises(FindingsParseError):
            extract_findings("# Review Report\n\nnothing\n")

    def test_empty_findings_array_is_valid(self) -> None:
        envelope = extract_findings(findings_message([]))
        self.assertEqual(envelope.findings, [])


class ExecutorTests(GitCase):
    def test_isolated_argv_has_no_key_and_disables_user_config(self) -> None:
        settings = CodexSettings(model="deepseek-flash")
        argv = build_argv(
            settings,
            executable="codex.cmd",
            cwd=self.repo,
            prompt="prompt-text",
        )
        joined = " ".join(argv)
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("env_key=", joined)
        self.assertNotIn("sk-", joined)
        self.assertIn("--ephemeral", argv)
        self.assertIn("read-only", argv)
        self.assertNotIn("--output-schema", argv)
        self.assertEqual(argv[-1], "-")

    def test_provider_model_is_pinned_to_flash(self) -> None:
        with self.assertRaises(ExecutorError):
            CodexSettings(model="deepseek-v4-pro").validate_model()

    def test_run_process_times_out_and_kills(self) -> None:
        started = time.monotonic()
        code, timed_out, _, _, duration_ms = run_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=self.repo,
            timeout_s=1,
        )
        elapsed = time.monotonic() - started
        self.assertTrue(timed_out)
        self.assertLess(elapsed, 20)
        self.assertGreaterEqual(duration_ms, 0)
        self.assertIsNotNone(code)


class ScopePolicyTests(unittest.TestCase):
    def test_denied_patterns(self) -> None:
        self.assertIsNotNone(deny_reason(".env"))
        self.assertIsNotNone(deny_reason("deep/.env.local"))
        self.assertIsNotNone(deny_reason("config/model-routing.yaml"))
        self.assertIsNotNone(deny_reason("lessons/01/slides.md"))
        self.assertIsNotNone(deny_reason("docs/archive/report.md"))
        self.assertIsNotNone(deny_reason("weights/model.gguf"))
        self.assertIsNone(deny_reason("CourseControl/src/course_control/cli.py"))
        self.assertIsNone(deny_reason("docs/PRD.md"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
