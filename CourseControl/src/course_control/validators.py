from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .authoring.shot_sheet import issues as sheet_issues
from .contracts import SLUG_RE
from .duration import (
    duplicate_authority_problem,
    planned_problems,
    resolve,
    window_problem,
)
from .paths import LessonPaths, is_under, path_problem
from .utils import ContractError, notes_blocks, page_budgets

FOUR_ELEMENTS = ("时长预算", "动画切入", "技术核查", "逐字口播")


@dataclass
class Issue:
    rule: str
    level: str
    message: str


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    def add(self, rule: str, level: str, message: str) -> None:
        self.issues.append(Issue(rule, level, message))

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def _strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<pre\b.*?</pre>", "", text, flags=re.S | re.I)
    text = re.sub(r"<code\b.*?</code>", "", text, flags=re.S | re.I)
    return re.sub(r"`[^`]*`", "", text)


def _page_count(slides_text: str) -> int:
    return sum(1 for line in slides_text.splitlines() if line.strip() == "---") + 1


def _asset_references(slides_text: str) -> list[str]:
    refs = re.findall(r'(?:src|href)="([^"]+)"', slides_text)
    refs += re.findall(r"!\[[^\]]*\]\(([^)]+)\)", slides_text)
    return [ref for ref in refs if ref.startswith("/")]


def _check_path(result: ValidationResult, label: str, value: str | None, *, allow_dir: bool = False) -> None:
    if value is None:
        return
    problem = path_problem(value, allow_dir=allow_dir)
    if problem:
        result.add("V-21", "error", f"{label}: {problem} ({value})")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_authoring(result: ValidationResult, paths: LessonPaths, notes_text: str) -> None:
    lesson = paths.lesson
    authoring = lesson.authoring
    if authoring is None:
        return

    if authoring.script:
        script_path = paths.content_path(authoring.script)
        if not script_path.is_file():
            result.add("V-29", "error", f"authoring script not found: {authoring.script}")
        else:
            try:
                from .authoring.models import NarrationScript
                from .narration_course import check_script_against_notes

                script = NarrationScript.model_validate(
                    json.loads(script_path.read_text(encoding="utf-8"))
                )
                check_script_against_notes(notes_text, script)
            except Exception as exc:  # noqa: BLE001
                result.add("V-29", "error", f"script and notes disagree: {exc}")

    approval_rel = authoring.approval or "authoring/approval.json"
    approval_path = paths.content_path(approval_rel)
    if not approval_path.is_file():
        result.add("V-33", "error", f"authoring approval file not found: {approval_rel}")
    else:
        try:
            from .authoring.models import ApprovalFile

            approval = ApprovalFile.model_validate(
                json.loads(approval_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:  # noqa: BLE001
            result.add("V-33", "error", f"cannot read approval file: {exc}")
        else:
            for relative in (
                authoring.digest,
                authoring.brief,
                authoring.outline,
                authoring.script,
            ):
                if not relative:
                    continue
                target = paths.content_path(relative)
                if not target.is_file():
                    continue
                entry = approval.find(relative)
                if entry is None:
                    result.add("V-33", "error", f"no approval for {relative}")
                elif entry.sha256 != _sha256(target):
                    result.add("V-33", "error", f"approval hash is stale for {relative}")

    if authoring.digest:
        digest_path = paths.content_path(authoring.digest)
        if not digest_path.is_file():
            result.add("V-32", "error", f"source digest not found: {authoring.digest}")
        else:
            try:
                from .authoring.models import NarrationScript, Outline, SourceDigest

                digest = SourceDigest.model_validate(
                    json.loads(digest_path.read_text(encoding="utf-8"))
                )
                refs = {section.ref for section in digest.sections}
                if authoring.outline:
                    outline_path = paths.content_path(authoring.outline)
                    if outline_path.is_file():
                        outline = Outline.model_validate(
                            json.loads(outline_path.read_text(encoding="utf-8"))
                        )
                        for page in outline.pages:
                            unknown = sorted(set(page.source_refs) - refs)
                            if unknown:
                                result.add(
                                    "V-32",
                                    "error",
                                    f"outline slide {page.slide} has unknown refs: {unknown}",
                                )
                if authoring.script and paths.content_path(authoring.script).is_file():
                    script = NarrationScript.model_validate(
                        json.loads(paths.content_path(authoring.script).read_text(encoding="utf-8"))
                    )
                    for page in script.pages:
                        refs_used = set(page.source_refs)
                        for segment in page.segments:
                            refs_used.update(segment.source_refs)
                        unknown = sorted(refs_used - refs)
                        if unknown:
                            result.add(
                                "V-32",
                                "error",
                                f"script slide {page.slide} has unknown refs: {unknown}",
                            )
            except Exception as exc:  # noqa: BLE001
                result.add("V-32", "error", f"citation check failed: {exc}")


def _check_beat_sheet(result: ValidationResult, paths: LessonPaths) -> None:
    """The director beat sheet is part of the build gate when authored."""
    sheet_path = paths.lesson_dir / "authoring" / "beats.yaml"
    if not sheet_path.is_file():
        if paths.lesson.video_form == "long" and paths.lesson.compose.mode == "scene":
            result.add("V-35", "warning", "no director beat sheet: authoring/beats.yaml")
        return
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not meta_path.is_file():
        result.add("V-35", "error", "beats.yaml requires narration.meta.json (run narration first)")
        return
    from . import palette_gate
    from .beats import load_segments, load_sheet, validate_sheet
    from .grammar import try_load_registry

    try:
        sheet = load_sheet(sheet_path)
        segments = load_segments(meta_path)
    except Exception as exc:  # noqa: BLE001
        result.add("V-35", "error", f"invalid beat sheet: {exc}")
        return
    try:
        palette_ok = palette_gate.ok(palette_gate.report(paths.workspace, sheet.palette))
    except Exception:  # noqa: BLE001
        palette_ok = False
    for issue in validate_sheet(
        sheet, segments, palette_ok=palette_ok, registry=try_load_registry(paths.workspace)
    ):
        result.add("V-35", "error", issue)


def _validate_shots(paths: LessonPaths, result: ValidationResult) -> ValidationResult:
    """Validation path for shot-driven productions (no page contract)."""
    from .grammar import try_load_registry
    from .production import validate_plan

    plan = paths.production
    if plan is None:
        result.add("V-40", "error", "shots mode requires a production contract")
        return result
    registry = try_load_registry(paths.workspace)
    for issue in validate_plan(
        plan, workspace=paths.workspace, engine_roots=paths.engine_roots, registry=registry
    ):
        result.add("V-40", "error", issue)
    if paths.production_source is not None:
        _check_path(result, "production", str(paths.production_source.relative_to(paths.lesson_dir)).replace("\\", "/"))
    lesson = paths.lesson
    if lesson.narration.enabled:
        source = lesson.narration.source or "narration.wav"
        narration = paths.narration_path(source)
        if not narration.is_file():
            result.add("V-41", "error", f"narration not found: {narration}")
    if lesson.subtitles.enabled:
        if lesson.subtitles.mode == "word":
            source = lesson.subtitles.word_source or "quality/asr-alignment.json"
            if not paths.build_path(source).is_file():
                result.add("V-41", "error", f"word captions require {source}")
        else:
            subtitles = paths.subtitles_path()
            if subtitles is None or not subtitles.is_file():
                result.add("V-41", "error", "subtitles enabled but file not found")
    policy = resolve(lesson)
    if policy is not None:
        for problem in planned_problems(plan.total_seconds, policy):
            result.add("V-26", problem.level, problem.message)
    notes = paths.content_path(lesson.content.notes)
    if notes.is_file():
        _check_authoring(result, paths, notes.read_text(encoding="utf-8"))
    _check_beat_sheet(result, paths)
    return result


def validate(paths: LessonPaths) -> ValidationResult:
    result = ValidationResult()
    lesson = paths.lesson

    if not SLUG_RE.match(paths.slug) or lesson.lesson_id != paths.lesson_dir.name:
        result.add("V-01", "error", "lesson_id must be a slug and match the directory name")

    if lesson.compose.mode == "shots":
        return _validate_shots(paths, result)

    content = lesson.content
    required = {
        "slides": paths.content_path(content.slides),
        "notes": paths.content_path(content.notes),
        "storyboard": paths.content_path(content.storyboard),
    }
    for name, path in required.items():
        if not path.is_file():
            result.add("V-02", "error", f"missing {name} file: {path}")
    if lesson.compose.mode == "recording":
        base = paths.base_video_path()
        if base is None:
            result.add("V-02", "error", "recording mode requires compose.base_video")
        elif not base.is_file():
            result.add("V-02", "error", f"base video not found: {base}")
    if content.outline and not paths.content_path(content.outline).is_file():
        result.add("V-02", "error", f"outline not found: {content.outline}")

    _check_path(result, "content.slides", content.slides)
    _check_path(result, "content.notes", content.notes)
    _check_path(result, "content.storyboard", content.storyboard)
    _check_path(result, "content.assets", content.assets, allow_dir=True)
    _check_path(result, "content.outline", content.outline)
    _check_path(result, "content.subtitles", content.subtitles)
    _check_path(result, "compose.base_video", lesson.compose.base_video)
    _check_path(result, "narration.source", lesson.narration.source)
    if lesson.authoring is not None:
        for label, value in (
            ("authoring.sources", lesson.authoring.sources),
            ("authoring.digest", lesson.authoring.digest),
            ("authoring.brief", lesson.authoring.brief),
            ("authoring.outline", lesson.authoring.outline),
            ("authoring.script", lesson.authoring.script),
            ("authoring.approval", lesson.authoring.approval),
        ):
            _check_path(result, label, value)
    for shot in paths.storyboard.shots:
        scene = shot.scene.split("::", 1)[0] if shot.engine == "manim" else shot.scene
        _check_path(result, f"shot {shot.id}.scene", scene)
        _check_path(result, f"shot {shot.id}.blend_task", shot.blend_task)
    for issue in sheet_issues(paths):
        result.add(issue["rule"], issue["level"], issue["message"])

    slides_text = required["slides"].read_text(encoding="utf-8")
    notes_text = required["notes"].read_text(encoding="utf-8")
    pages = _page_count(slides_text)
    blocks = notes_blocks(notes_text)

    if pages != len(blocks):
        result.add("V-03", "error", f"slides has {pages} pages but notes has {len(blocks)} blocks")
    for label, block in blocks:
        missing = [element for element in FOUR_ELEMENTS if element not in block]
        if missing:
            result.add("V-04", "error", f"Slide {label} missing: {', '.join(missing)}")

    policy = resolve(lesson)
    if policy is not None:
        duplicate = duplicate_authority_problem(lesson, policy)
        if duplicate is not None:
            result.add("V-26", duplicate.level, duplicate.message)
        if lesson.narration.timing == "measured":
            meta_path = paths.build_root / "narration" / "narration.meta.json"
            if not meta_path.is_file():
                result.add(
                    "V-26",
                    "warning",
                    "narration.timing=measured but narration.meta.json is not generated yet",
                )
            else:
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    measured = float((meta.get("assembly") or {}).get("duration_s") or 0.0)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    result.add("V-26", "error", f"cannot read narration.meta.json: {exc}")
                else:
                    problem = window_problem(measured, policy)
                    if problem is not None:
                        result.add("V-26", problem.level, problem.message)
        else:
            try:
                budgets = page_budgets(notes_text)
            except ContractError as exc:
                result.add("V-26", "error", str(exc))
            else:
                for problem in planned_problems(sum(budgets), policy):
                    result.add("V-26", problem.level, problem.message)

    _check_authoring(result, paths, notes_text)
    _check_beat_sheet(result, paths)

    for ref in _asset_references(slides_text):
        prefix = f"/lessons/{paths.slug}/assets/"
        if not ref.startswith(prefix):
            result.add("V-05", "error", f"asset path must start with {prefix}: {ref}")
            continue
        target = (paths.lesson_dir / ref[len(f"/lessons/{paths.slug}/"):]).resolve()
        if not is_under(paths.lesson_dir, target) or not target.is_file():
            result.add("V-05", "error", f"asset not found: {ref}")

    clean = _strip_code(slides_text)
    if re.search(r"notes?\s*:", clean, re.I):
        result.add("V-06", "error", "slides.md contains Notes:")
    if "<video" in clean.lower():
        result.add("V-06", "error", "slides.md contains <video>")
    if "[ANIMATION" in clean:
        result.add("V-06", "error", "slides.md contains [ANIMATION]")
    if "$$" in clean or re.search(r"(?<!\\)\$[^$\n]+\$", clean):
        result.add("V-06", "error", "slides.md contains $...$ math delimiters")

    ids: set[str] = set()
    for shot in paths.storyboard.shots:
        if shot.id in ids:
            result.add("V-07", "error", f"duplicate shot id: {shot.id}")
        ids.add(shot.id)
        if shot.slide > pages:
            result.add("V-07", "error", f"shot {shot.id} references slide {shot.slide} > {pages}")
        if shot.engine not in lesson.engines:
            result.add("V-07", "error", f"shot {shot.id} engine {shot.engine} not in lesson.engines")

        scene_path, _ = paths.scene_path(shot)
        if not scene_path.is_file():
            result.add("V-08", "error", f"shot {shot.id} scene not found: {scene_path}")
        if shot.engine == "blender" and not shot.blend_task:
            result.add("V-07", "error", f"blender shot {shot.id} requires blend_task")
        if shot.blend_task:
            task_path = paths.blend_task_path(shot)
            if task_path is None or not task_path.is_file():
                result.add("V-08", "error", f"blend task not found: {shot.blend_task}")

    if "motion_canvas" in lesson.engines:
        project_file = paths.engine_root("motion_canvas") / "src" / "project.ts"
        project_text = project_file.read_text(encoding="utf-8") if project_file.is_file() else ""
        for shot in paths.storyboard.shots:
            if shot.engine != "motion_canvas":
                continue
            scene_path, _ = paths.scene_path(shot)
            stem = scene_path.stem
            if stem not in project_text:
                result.add(
                    "V-09",
                    "error",
                    f"motion scene '{stem}' is not registered in src/project.ts",
                )

    _check_formula_bindings(paths, result)
    return result


def formula_binding_problems(shots, formula_dir: Path) -> list[str]:
    """Check that shot formula_ids resolve to unique FormulaSpec files."""
    if not formula_dir.is_dir():
        return []
    from .formulas import FormulaSpec, source_problems

    specs: dict[str, FormulaSpec] = {}
    problems: list[str] = []
    for path in sorted(formula_dir.glob("*.json")):
        try:
            spec = FormulaSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name}: invalid FormulaSpec: {exc}")
            continue
        if spec.formula_id in specs:
            problems.append(f"{path.name}: duplicate formula_id {spec.formula_id}")
            continue
        specs[spec.formula_id] = spec
        for issue in source_problems(spec):
            if issue.level == "error":
                problems.append(f"{spec.formula_id}: {issue.message}")
        if spec.validation.latex_compile == "fail":
            problems.append(f"{spec.formula_id}: latex_compile is fail")
    referenced: set[str] = set()
    for shot in shots:
        for formula_id in getattr(shot, "formula_ids", []) or []:
            referenced.add(formula_id)
            if formula_id not in specs:
                problems.append(f"shot {shot.id}: unknown formula_id {formula_id}")
    for formula_id in sorted(set(specs) - referenced):
        problems.append(f"formula {formula_id} is not referenced by any shot")
    return problems


def _check_formula_bindings(paths, result) -> None:
    lesson_dir = getattr(paths, "lesson_dir", None)
    if lesson_dir is None:
        return
    problems = formula_binding_problems(
        paths.storyboard.shots, Path(lesson_dir) / "authoring" / "formulas"
    )
    for problem in problems:
        result.add("V-34", "error", problem)
