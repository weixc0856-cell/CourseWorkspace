from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .contracts import Artifact, BuildReport, CheckRecord, StageRecord, Status
from .duration import resolve
from .paths import LessonPaths, path_problem
from .utils import probe_media, run_command, which_command


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def toolchain_versions(workspace: Path) -> dict[str, str]:
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    commands = {
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "uv": ["uv", "--version"],
        "ffmpeg": ["ffmpeg", "-version"],
    }
    for name, command in commands.items():
        result = run_command([*which_command(command[0]), *command[1:]], workspace, timeout=30)
        if result.exit_code == 0:
            versions[name] = result.stdout.splitlines()[0].strip() if result.stdout else "unknown"
    config_path = workspace / "config" / "tools.yaml"
    if config_path.is_file():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            blender = (config.get("blender") or {}).get("executable")
            if blender:
                result = run_command([str(blender), "--version"], workspace, timeout=30)
                if result.exit_code == 0 and result.stdout:
                    versions["blender"] = result.stdout.splitlines()[0].strip()
        except Exception:  # noqa: BLE001
            pass
    return versions


class ReportBuilder:
    def __init__(self, paths: LessonPaths):
        self.paths = paths
        self.run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        self.started_at = _now()
        self.stages: list[StageRecord] = []
        self.checks: list[CheckRecord] = []
        self.artifacts: list[Artifact] = []
        self.failures: list[str] = []

    def add_stage(self, outcome) -> None:
        self.stages.append(
            StageRecord(
                name=outcome.name,
                status=outcome.status,
                started_at=self.started_at,
                finished_at=_now(),
                duration_ms=outcome.duration_ms,
                outputs=[str(path) for path in outcome.outputs],
                warnings=list(outcome.warnings),
                errors=list(outcome.errors),
                reason=outcome.reason,
            )
        )

    def add_check(self, check_id: str, status: Status, expected: str | None = None, actual: str | None = None, detail: str | None = None) -> None:
        self.checks.append(CheckRecord(id=check_id, status=status, expected=expected, actual=actual, detail=detail))

    def collect_artifacts(self) -> None:
        seen: set[Path] = set()
        candidates: list[Path] = []
        for stage in self.stages:
            candidates.extend(Path(item) for item in stage.outputs)
        final_dir = self.paths.build_root / "final"
        if final_dir.is_dir():
            candidates.extend(path for path in final_dir.rglob("*") if path.is_file())
        report_path = self.paths.build_root / "final" / "build-report.json"
        for path in candidates:
            if not path.is_file() or path in seen or path.resolve() == report_path.resolve():
                continue
            seen.add(path)
            try:
                relative = path.resolve().relative_to(self.paths.build_root.resolve()).as_posix()
            except ValueError:
                self.failures.append(f"artifact outside build/{self.paths.slug}: {path}")
                continue
            probe = None
            if path.suffix.lower() in (".mp4", ".png", ".jpg", ".jpeg", ".webm", ".wav", ".mp3"):
                try:
                    probe = probe_media(path).as_dict()
                except Exception:  # noqa: BLE001
                    probe = None
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            self.artifacts.append(
                Artifact(
                    path=relative,
                    kind=path.suffix.lower().lstrip(".") or "file",
                    size_bytes=path.stat().st_size,
                    sha256=digest.hexdigest(),
                    probe=probe,
                )
            )

    def _statuses(self):
        return [stage.status for stage in self.stages] + [check.status for check in self.checks]

    def _verdict(self) -> str:
        statuses = self._statuses()
        if any(status == Status.FAIL for status in statuses):
            return "fail"
        if any(status in (Status.SKIPPED, Status.NOT_RUN) for status in statuses):
            return "incomplete"
        return "pass"

    def _applicability_errors(self) -> list[str]:
        errors: list[str] = []
        stages = {stage.name: stage.status for stage in self.stages}
        for engine in ("motion_canvas", "manim", "blender", "code_video"):
            name = f"render:{engine}"
            status = stages.get(name)
            if (
                status not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE)
                and engine not in self.paths.lesson.engines
            ):
                errors.append(f"{name} must be not_applicable")
        capture = stages.get("capture_slides")
        if (
            self.paths.lesson.compose.mode == "recording"
            and capture not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE)
        ):
            errors.append("capture_slides must be not_applicable in recording mode")
        checks = {check.id: check.status for check in self.checks}
        if not self.paths.lesson.narration.enabled and checks.get("V-15") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-15 must be not_applicable when narration is disabled")
        if not self.paths.lesson.subtitles.enabled and checks.get("V-16") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-16 must be not_applicable when subtitles are disabled")
        if self.paths.lesson.compose.mode == "deck" and checks.get("V-20") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-20 must be not_applicable in deck mode")
        if resolve(self.paths.lesson) is None and checks.get("V-27") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-27 must be not_applicable when no duration policy is declared")
        burn_in = self.paths.lesson.subtitles.enabled and self.paths.lesson.subtitles.render == "burn_in"
        if not burn_in and checks.get("V-28") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-28 must be not_applicable when burn-in is disabled")
        if not (self.paths.lesson.narration.enabled and self.paths.lesson.narration.timing == "measured") and checks.get("V-30") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-30 must be not_applicable unless measured narration is enabled")
        if not self.paths.lesson.subtitles.enabled and checks.get("V-31") not in (None, Status.NOT_RUN, Status.NOT_APPLICABLE):
            errors.append("V-31 must be not_applicable when subtitles are disabled")
        return errors

    def finalize(self) -> BuildReport:
        self.collect_artifacts()
        applicability = self._applicability_errors()
        self.add_check(
            "V-19",
            Status.PASS if not applicability else Status.FAIL,
            expected="stage and check applicability matches lesson.yaml",
            actual="ok" if not applicability else "; ".join(applicability),
        )

        structural: list[str] = []
        if not self.stages:
            structural.append("no stages recorded")
        for stage in self.stages:
            if not stage.started_at:
                structural.append(f"{stage.name} has no started_at")
        verdict_before = self._verdict()
        self.add_check(
            "V-17",
            Status.PASS if not structural else Status.FAIL,
            expected="stages present; verdict follows status rules",
            actual=f"verdict={verdict_before}, stages={len(self.stages)}",
            detail="; ".join(structural) if structural else None,
        )

        verdict = self._verdict()
        failures = list(self.failures)
        for stage in self.stages:
            if stage.status == Status.FAIL:
                failures.extend(f"{stage.name}: {error}" for error in stage.errors)
            elif stage.status in (Status.SKIPPED, Status.NOT_RUN):
                failures.append(f"{stage.name}: {stage.reason or stage.status.value}")
        for check in self.checks:
            if check.status == Status.FAIL:
                failures.append(f"{check.id}: {check.detail or check.actual or 'failed'}")
        if verdict != "pass" and not failures:
            failures.append(f"verdict is {verdict} but no failure detail was recorded")

        return BuildReport(
            run_id=self.run_id,
            lesson=self.paths.slug,
            started_at=self.started_at,
            finished_at=_now(),
            toolchain=toolchain_versions(self.paths.workspace),
            stages=self.stages,
            artifacts=self.artifacts,
            checks=self.checks,
            verdict=verdict,
            failures=failures,
        )

    def write(self, report: BuildReport) -> Path:
        target = self.paths.build_root / "final" / "build-report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return target


def check_report_payload(paths: LessonPaths, data: dict) -> CheckRecord:
    """Validate an existing build-report.json against V-17."""
    errors: list[str] = []
    if data.get("lesson") != paths.slug:
        errors.append(f"lesson mismatch: {data.get('lesson')}")
    stages = data.get("stages") or []
    checks = data.get("checks") or []
    if not stages:
        errors.append("no stages")
    statuses = [stage.get("status") for stage in stages] + [check.get("status") for check in checks]
    if any(status == "fail" for status in statuses):
        expected = "fail"
    elif any(status in ("skipped", "not_run") for status in statuses):
        expected = "incomplete"
    else:
        expected = "pass"
    if data.get("verdict") != expected:
        errors.append(f"verdict {data.get('verdict')} != expected {expected}")
    if expected != "pass" and not data.get("failures"):
        errors.append("non-pass verdict has empty failures[]")
    for artifact in data.get("artifacts") or []:
        problem = path_problem(artifact.get("path", ""))
        if problem:
            errors.append(f"artifact path: {problem}")
    return CheckRecord(
        id="V-17",
        status=Status.PASS if not errors else Status.FAIL,
        expected="report complete and verdict consistent",
        actual="ok" if not errors else "; ".join(errors),
    )
