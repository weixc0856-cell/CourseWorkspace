"""Read-only audit of a production content root.

``check.ps1`` proves the code against an isolated development root; it never
reads a course. This audit is the other half: it checks the content root that
actually holds lessons, builds and deliveries, and it never writes there.

The rules are the ones already enforced elsewhere (layout contract, lesson
contract, course chain, delivery manifest schema). The audit adds no gate of
its own; it only reports what the existing rules say about the real tree.
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path

PASS = "pass"
WARN = "warn"
INFO = "info"
FAIL = "fail"

LEFTOVER_SUFFIXES = (".tmp", ".old")


@dataclass
class Finding:
    area: str
    status: str
    detail: str


@dataclass
class AuditResult:
    root: Path
    findings: list[Finding] = field(default_factory=list)

    def add(self, area: str, status: str, detail: str) -> None:
        self.findings.append(Finding(area, status, detail))

    @property
    def errors(self) -> list[Finding]:
        return [item for item in self.findings if item.status == FAIL]

    @property
    def warnings(self) -> list[Finding]:
        return [item for item in self.findings if item.status == WARN]

    def status(self, *, strict: bool = False) -> str:
        if self.errors:
            return FAIL
        if strict and self.warnings:
            return FAIL
        if self.warnings:
            return "incomplete"
        return PASS

    def as_dict(self, *, strict: bool = False) -> dict:
        return {
            "content_root": str(self.root),
            "status": self.status(strict=strict),
            "counts": {
                key: sum(1 for item in self.findings if item.status == key)
                for key in (PASS, WARN, INFO, FAIL)
            },
            "findings": [
                {"area": item.area, "status": item.status, "detail": item.detail}
                for item in self.findings
            ],
        }


def _script_module(workspace: Path, name: str):
    path = Path(workspace).resolve() / "scripts" / name
    if not path.is_file():
        raise FileNotFoundError(f"audit script not found: {path}")
    spec = importlib.util.spec_from_file_location(f"cw_audit_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audit_layout(workspace: Path, root: Path, result: AuditResult) -> None:
    build = root / "build"
    if not build.is_dir():
        result.add("layout", WARN, f"no build directory: {build}")
        return
    module = _script_module(workspace, "check_build_layout.py")
    errors, _advice, _seen = module.audit(
        build,
        root / "lessons",
        Path(workspace).resolve() / "CourseControl" / "tests" / "fixtures",
        root / "projects",
    )
    if errors:
        for item in errors:
            result.add("layout", FAIL, item)
    else:
        result.add("layout", PASS, "build/ top level matches the layout contract")


def _audit_lessons(workspace: Path, root: Path, result: AuditResult) -> None:
    """Source contract and approval freshness, not build state.

    Downstream artifacts (narration, beats, scenes) are the build's business;
    the content audit answers what a lesson *is* and whether the human
    approvals still match it.
    """
    from course_control.content.paths import LessonPaths
    from course_control.content.validators import approval_problems

    lessons = root / "lessons"
    if not lessons.is_dir():
        result.add("lessons", WARN, f"no lessons directory: {lessons}")
        return
    checked = 0
    failed = 0
    for lesson in sorted(lessons.iterdir()):
        if not lesson.is_dir() or not (lesson / "lesson.yaml").is_file():
            continue
        checked += 1
        try:
            paths = LessonPaths.load(
                Path(workspace).resolve(),
                lesson,
                build_root_override=root / "build" / lesson.name,
            )
        except Exception as exc:  # noqa: BLE001 - a broken lesson is a finding
            failed += 1
            result.add("lessons", FAIL, f"{lesson.name}: {exc}")
            continue
        content = paths.lesson.content
        for label, relative in (
            ("slides", content.slides),
            ("notes", content.notes),
            ("storyboard", content.storyboard),
        ):
            if relative and not (lesson / relative).is_file():
                failed += 1
                result.add("lessons", FAIL, f"{lesson.name}: missing {label} {relative}")
        for problem in approval_problems(paths):
            failed += 1
            result.add("lessons", FAIL, f"{lesson.name}: {problem}")
    if checked == 0:
        result.add("lessons", WARN, "no lesson.yaml under lessons/")
    elif failed == 0:
        result.add("lessons", PASS, f"{checked} lesson(s) have their source and approvals")


def _audit_chain(workspace: Path, root: Path, result: AuditResult) -> None:
    from course_control.production.course_chain import (
        check_lesson_course_chain,
        default_chain_config,
    )

    lessons = root / "lessons"
    if not lessons.is_dir():
        return
    checked = 0
    failed = 0
    for lesson in sorted(lessons.iterdir()):
        if not lesson.is_dir() or not (lesson / "lesson.yaml").is_file():
            continue
        try:
            chain = check_lesson_course_chain(
                Path(workspace).resolve(),
                lesson,
                config_path=default_chain_config(),
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            result.add("chain", FAIL, f"{lesson.name}: {exc}")
            continue
        if chain is None:
            continue
        checked += 1
        for error in chain.errors:
            failed += 1
            result.add("chain", FAIL, f"{lesson.name}: {error}")
    if checked and failed == 0:
        result.add("chain", PASS, f"{checked} bound lesson(s) match their course plan")


def _audit_delivery(root: Path, result: AuditResult) -> None:
    deliver = root / "deliver"
    if not deliver.is_dir():
        result.add("deliver", WARN, f"no deliver directory: {deliver}")
        return
    classified = 0
    for entry in sorted(deliver.iterdir()):
        name = entry.name
        if not entry.is_dir():
            continue
        if name.endswith(LEFTOVER_SUFFIXES):
            result.add(
                "deliver",
                WARN,
                f"{name}: leftover scratch directory from an interrupted package",
            )
            continue
        if name.endswith(".attempt"):
            result.add(
                "deliver",
                INFO,
                f"{name}: failed package kept for inspection, not a delivery",
            )
            continue
        manifest = entry / "manifest.json"
        if not manifest.is_file():
            result.add(
                "deliver", WARN, f"{name}: no manifest.json; classify as history or remove"
            )
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            result.add("deliver", WARN, f"{name}: unreadable manifest: {exc}")
            continue
        classified += 1
        schema = data.get("schema_version")
        verdict = data.get("verdict")
        if schema == 1:
            result.add(
                "deliver",
                INFO,
                f"{name}: schema 1 (historical); package-verify on the current "
                "verifier will refuse it",
            )
        elif verdict != "pass":
            result.add("deliver", WARN, f"{name}: manifest verdict is {verdict!r}")
    if classified:
        result.add("deliver", PASS, f"{classified} package(s) carry a manifest")


def run_audit(workspace: Path, *, strict: bool = False) -> AuditResult:
    from course_control.platform.workspace_layout import content_root

    root = content_root(Path(workspace).resolve())
    result = AuditResult(root)
    _audit_layout(Path(workspace), root, result)
    _audit_lessons(Path(workspace), root, result)
    _audit_chain(Path(workspace), root, result)
    _audit_delivery(root, result)
    return result
