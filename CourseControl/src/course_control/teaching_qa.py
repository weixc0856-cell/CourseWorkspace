"""Teaching QA: deterministic structural checks plus an explicit evidence gap.

The report can prove that objectives, pages, examples and a recap are present.
It cannot prove that learners understand the lesson, so its status is never
PASS: ``learner_evidence`` stays ``missing`` until real learner results exist.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .paths import LessonPaths

PASS = "PASS"
WARN = "WARN"
BLOCKED = "BLOCKED"
INCOMPLETE = "INCOMPLETE"

EXAMPLE_MARKERS = re.compile(
    r"\b(for example|for instance|consider|imagine|suppose|take a|e\.g\.)\b",
    re.IGNORECASE,
)
MISCONCEPTION_MARKERS = re.compile(
    r"\b(not |unlike|rather than|common mistake|misconception|people often|you might think)\b",
    re.IGNORECASE,
)
RECAP_MARKERS = re.compile(
    r"\b(summary|recap|one picture|in summary|next step|where to go)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _check(check_id: str, status: str, detail: str, **values) -> dict:
    return {"id": check_id, "status": status, "detail": detail, **values}


def run_teaching_qa(workspace: Path, paths: LessonPaths) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    build_root = paths.build_root
    lesson_dir = paths.lesson_dir
    lesson = paths.lesson
    checks: list[dict] = []
    errors: list[str] = []

    narrative = _load(build_root / "quality" / "narrative.json")
    if narrative is None:
        checks.append(
            _check("teaching.narrative", INCOMPLETE, "no narrative validation report")
        )
    else:
        beat_ids = {beat.get("id") for beat in narrative.get("beats", [])}
        checks.append(
            _check(
                "teaching.narrative",
                PASS if narrative.get("status") in {"pass", "warn"} else BLOCKED,
                f"narrative status={narrative.get('status')}",
                beats=sorted(beat_ids),
            )
        )

    brief_path = None
    outline_path = None
    script_path = None
    if lesson.authoring is not None:
        if lesson.authoring.brief:
            brief_path = lesson_dir / lesson.authoring.brief
        if lesson.authoring.outline:
            outline_path = lesson_dir / lesson.authoring.outline
        if lesson.authoring.script:
            script_path = lesson_dir / lesson.authoring.script

    brief = _load(brief_path) if brief_path else None
    outline = _load(outline_path) if outline_path else None
    script = _load(script_path) if script_path else None

    if brief is None:
        checks.append(_check("teaching.objectives", INCOMPLETE, "no brief/objectives"))
    else:
        objectives = [str(item) for item in brief.get("objectives") or []]
        pages = (
            [
                page
                for chapter in (outline or {}).get("chapters", [])
                for page in chapter.get("pages", [])
            ]
            if outline
            else []
        )
        page_tokens = [
            _tokens(f"{page.get('title', '')} {page.get('claim', '')}") for page in pages
        ]
        uncovered = []
        for objective in objectives:
            tokens = _tokens(objective)
            if not any(len(tokens & page) / max(1, len(tokens)) >= 0.15 for page in page_tokens):
                uncovered.append(objective)
        checks.append(
            _check(
                "teaching.objectives",
                PASS if objectives and not uncovered else WARN,
                f"{len(objectives)} objective(s); {len(uncovered)} not mapped to a page",
                uncovered=uncovered,
            )
        )

    if outline is None:
        checks.append(_check("teaching.pages", INCOMPLETE, "no outline/pages"))
        pages = []
    else:
        pages = [
            page
            for chapter in outline.get("chapters", [])
            for page in chapter.get("pages", [])
        ]
        bad = [page for page in pages if not str(page.get("claim") or "").strip()]
        checks.append(
            _check(
                "teaching.pages",
                PASS if pages and not bad else WARN,
                f"{len(pages)} page(s); {len(bad)} without a claim",
            )
        )

    if script is None:
        checks.append(_check("teaching.narration", INCOMPLETE, "no narration script"))
        script_pages = []
    else:
        script_pages = script.get("pages") or []
        checks.append(
            _check(
                "teaching.narration",
                PASS if len(script_pages) == len(pages) else WARN,
                f"{len(script_pages)} narration page(s); {len(pages)} outline page(s)",
            )
        )

    script_text = json.dumps(script or {}, ensure_ascii=False)
    checks.append(
        _check(
            "teaching.examples",
            PASS if EXAMPLE_MARKERS.search(script_text) else WARN,
            "example markers found" if EXAMPLE_MARKERS.search(script_text) else "no example marker",
        )
    )
    checks.append(
        _check(
            "teaching.misconceptions",
            PASS if MISCONCEPTION_MARKERS.search(script_text) else WARN,
            "misconception markers found"
            if MISCONCEPTION_MARKERS.search(script_text)
            else "no misconception marker",
        )
    )

    slides_text = ""
    slides_path = lesson_dir / lesson.content.slides
    if slides_path.is_file():
        slides_text = slides_path.read_text(encoding="utf-8")
    page_blocks = re.split(r"(?m)^\s*---\s*$", slides_text)
    bullets = [
        sum(1 for line in block.splitlines() if line.strip().startswith(("- ", "* ")))
        for block in page_blocks
        if block.strip()
    ]
    heavy = [index + 1 for index, count in enumerate(bullets) if count > 8]
    checks.append(
        _check(
            "teaching.cognitive_load",
            PASS if not heavy else WARN,
            f"max bullets/page={max(bullets) if bullets else 0}; heavy pages={heavy}",
        )
    )

    last_page_text = ""
    if pages:
        last_page_text = f"{pages[-1].get('title', '')} {pages[-1].get('claim', '')}"
    has_recap = bool(RECAP_MARKERS.search(last_page_text or script_text))
    checks.append(
        _check(
            "teaching.closure",
            PASS if has_recap else WARN,
            "recap/closure marker found" if has_recap else "no recap marker on the last page",
        )
    )

    checks.append(
        _check(
            "teaching.learner_evidence",
            INCOMPLETE,
            "no real learner test; AI simulation cannot prove understanding",
        )
    )

    structural = [
        check for check in checks if check["id"] != "teaching.learner_evidence"
    ]
    structural_status = PASS
    if any(check["status"] == BLOCKED for check in structural):
        structural_status = BLOCKED
    elif any(check["status"] == INCOMPLETE for check in structural):
        structural_status = INCOMPLETE
    elif any(check["status"] == WARN for check in structural):
        structural_status = WARN

    report = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": _now(),
        "status": WARN,
        "structural_status": structural_status,
        "learner_evidence": "missing",
        "checks": checks,
        "errors": errors,
        "summary": "structural teaching checks only; learner evidence is missing",
    }
    target = build_root / "quality" / "teaching-qa.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report, target


__all__ = ["BLOCKED", "INCOMPLETE", "PASS", "WARN", "run_teaching_qa"]
