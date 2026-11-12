"""Formula pipeline: one LaTeX source, static KaTeX render, independent checks.

The formula is a first-class production asset, not decorative text. This module
owns the FormulaSpec contract, structural LaTeX checks, the KaTeX render call,
and the audit record. It deliberately does not claim mathematical correctness:
that status stays ``pending`` until a human/source review records it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import Field

from course_control.content.contracts import StrictModel
from course_control.platform.utils import which_command

FormulaStatus = Literal["pending", "pass", "fail", "not_applicable", "unverified"]


class FormulaSymbol(StrictModel):
    name: str
    meaning: str
    unit: str | None = None


class FormulaSource(StrictModel):
    document: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    url: str | None = None


class FormulaValidation(StrictModel):
    latex_compile: FormulaStatus = "pending"
    mathematical_review: FormulaStatus = "pending"
    dimensional_check: FormulaStatus = "pending"
    visual_review: FormulaStatus = "pending"
    video_review: FormulaStatus = "pending"


class FormulaSpec(StrictModel):
    schema_version: Literal[1] = 1
    formula_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    latex: str = Field(min_length=1)
    display: Literal["block", "inline"] = "block"
    engine: Literal["katex", "mathjax"] = "katex"
    meaning: str = Field(min_length=1)
    symbols: dict[str, str] = Field(default_factory=dict)
    source: FormulaSource
    validation: FormulaValidation = Field(default_factory=FormulaValidation)
    font_size: int = Field(default=48, ge=12, le=160)
    color: str = "#252A31"


class FormulaIssue(StrictModel):
    stage: Literal["source", "compile", "math", "visual"]
    level: Literal["error", "warning"]
    message: str


class FormulaAudit(StrictModel):
    formula_id: str
    issues: list[FormulaIssue] = Field(default_factory=list)
    validation: FormulaValidation
    render: dict = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def _unescaped_percent(latex: str) -> bool:
    for index, char in enumerate(latex):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and latex[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return True
    return False


def _brace_problem(latex: str) -> str | None:
    depth = 0
    index = 0
    while index < len(latex):
        char = latex[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return "unbalanced closing brace"
        index += 1
    return "unbalanced opening brace" if depth else None


def source_problems(spec: FormulaSpec) -> list[FormulaIssue]:
    issues: list[FormulaIssue] = []
    latex = spec.latex
    if _unescaped_percent(latex):
        issues.append(
            FormulaIssue(
                stage="source",
                level="error",
                message=r"unescaped '%' starts a LaTeX comment; use '\%'",
            )
        )
    brace = _brace_problem(latex)
    if brace:
        issues.append(FormulaIssue(stage="source", level="error", message=brace))
    if "$" in latex:
        issues.append(
            FormulaIssue(
                stage="source",
                level="error",
                message="do not put $ delimiters in FormulaSpec.latex; the renderer owns delimiters",
            )
        )
    for forbidden in ("\\documentclass", "\\usepackage", "\\begin{document}", "\\input", "\\include"):
        if forbidden in latex:
            issues.append(
                FormulaIssue(
                    stage="source",
                    level="error",
                    message=f"forbidden full-document command: {forbidden}",
                )
            )
    if not spec.symbols:
        issues.append(
            FormulaIssue(
                stage="source",
                level="warning",
                message="formula has no symbol glossary",
            )
        )
    return issues


def math_problems(spec: FormulaSpec) -> list[FormulaIssue]:
    """Optional symbolic check; never promotes to a human mathematical review."""
    if spec.latex.count("=") != 1:
        return []
    try:
        from sympy import simplify  # type: ignore
        from sympy.parsing.latex import parse_latex  # type: ignore
    except Exception:
        return []
    left, right = spec.latex.split("=", 1)
    try:
        difference = simplify(parse_latex(left) - parse_latex(right))
    except Exception:
        return [
            FormulaIssue(
                stage="math",
                level="warning",
                message="symbolic check could not parse this formula; human review required",
            )
        ]
    if difference != 0:
        return [
            FormulaIssue(
                stage="math",
                level="error",
                message=f"symbolic check found a non-zero difference: {difference}",
            )
        ]
    return []


def _node() -> str:
    node = which_command("node")
    if not node:
        raise RuntimeError("node executable not found")
    return node[0]


def render_formula(
    spec: FormulaSpec,
    out_dir: Path,
    workspace: Path,
    *,
    engine: str | None = None,
) -> dict:
    remotion = workspace / "RemotionStudio"
    script = remotion / "scripts" / "formula-render.mjs"
    if not script.is_file():
        raise RuntimeError(f"formula renderer not found: {script}")
    spec_path = out_dir / "formula.spec.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    command = [
        _node(),
        str(script),
        "--spec",
        str(spec_path),
        "--out",
        str(out_dir / "render"),
        "--engine",
        engine or spec.engine,
    ]
    result = subprocess.run(
        command,
        cwd=remotion,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"KaTeX render failed ({result.returncode}): {(result.stderr or result.stdout)[-1200:]}"
        )
    payload = json.loads((out_dir / "render" / "formula.render.json").read_text(encoding="utf-8"))
    if payload.get("invisible_glyphs"):
        raise RuntimeError("KaTeX produced an error glyph")
    if payload.get("width", 0) < 4 or payload.get("height", 0) < 4:
        raise RuntimeError("rendered formula is empty")
    return payload


def audit_formula(spec: FormulaSpec, out_dir: Path, workspace: Path) -> FormulaAudit:
    issues = source_problems(spec)
    render: dict = {}
    validation = spec.validation.model_copy()
    if not any(issue.stage == "source" and issue.level == "error" for issue in issues):
        try:
            render = render_formula(spec, out_dir, workspace)
            validation.latex_compile = "pass"
            validation.visual_review = "pass"
        except Exception as exc:  # noqa: BLE001
            validation.latex_compile = "fail"
            issues.append(FormulaIssue(stage="compile", level="error", message=str(exc)))
    else:
        validation.latex_compile = "fail"
    issues.extend(math_problems(spec))
    audit = FormulaAudit(
        formula_id=spec.formula_id,
        issues=issues,
        validation=validation,
        render=render,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "formula.audit.json").write_text(
        json.dumps(audit.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit


def load_spec(path: Path) -> FormulaSpec:
    return FormulaSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
