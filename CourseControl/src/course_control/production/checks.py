from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from course_control.production.quality_rubric import CheckSpec, QualityRubric

Status = Literal["pass", "fail", "review", "not_run"]


@dataclass
class EvalContext:
    spec: Any
    lesson_dir: Path
    build_root: Path
    book_index: Path | None = None


@dataclass
class CheckResult:
    id: str
    kind: str
    severity: str
    status: Status
    actual: Any = None
    expected: Any = None
    evidence: str | None = None
    prompt: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "severity": self.severity,
            "status": self.status,
            "actual": self.actual,
            "expected": self.expected,
            "evidence": self.evidence,
            "prompt": self.prompt,
            "detail": self.detail,
        }


def _source_matches(entry: dict, source: Any) -> bool:
    def same(a: Any, b: Any) -> bool:
        return str(a).strip().lower() == str(b).strip().lower()

    if not same(entry.get("chapter"), getattr(source, "chapter", None)):
        return False
    for key in ("section", "figure", "table"):
        want = getattr(source, key, None)
        if want and not same(entry.get(key), want):
            return False
    page = getattr(source, "page", None)
    if page and entry.get("page") != page:
        return False
    return True


def _claim_source(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    claims = getattr(ctx.spec, "claims", None)
    if not claims:
        return "not_run", None, "claims with sources", "spec"
    if ctx.book_index is None or not ctx.book_index.is_file():
        return "not_run", None, "book/index.json", str(ctx.book_index or "book/index.json")
    try:
        index = json.loads(ctx.book_index.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "fail", str(exc), "readable book index", str(ctx.book_index)
    entries = index.get("sources") if isinstance(index, dict) else None
    if not isinstance(entries, list) or not entries:
        return "fail", 0, ">=1 indexed source", str(ctx.book_index)
    missing = [
        getattr(c, "id", "?")
        for c in claims
        if not any(_source_matches(e, getattr(c, "source", None)) for e in entries)
    ]
    if missing:
        return "fail", missing, "every claim resolves in book index", str(ctx.book_index)
    return "pass", len(claims), len(claims), str(ctx.book_index)


def _duration(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    total = getattr(ctx.spec, "total_seconds", None)
    lo = getattr(ctx.spec, "min_seconds", None)
    hi = getattr(ctx.spec, "max_seconds", None)
    if total is None or lo is None or hi is None:
        return "not_run", None, "duration window", "spec"
    ok = lo <= total <= hi
    return ("pass" if ok else "fail"), total, [lo, hi], "beats"


def _voice(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    voice = getattr(ctx.spec, "voice", None)
    if not isinstance(voice, dict):
        return "not_run", None, "voice status", "spec"
    status = str(voice.get("status") or "").strip()
    ok = status in {"owner", "cloud", "local", "none"}
    return ("pass" if ok else "fail"), status or None, "owner|cloud|local|none", "authoring/episode.spec.yaml"


def _rights(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    rights = getattr(ctx.spec, "rights", None)
    if not isinstance(rights, dict):
        return "not_run", None, "rights.figures_checked", "spec"
    ok = bool(rights.get("figures_checked"))
    return ("pass" if ok else "fail"), ok, True, "authoring/episode.spec.yaml"


def _drivaer(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    assets = getattr(ctx.spec, "assets", None)
    if not isinstance(assets, list):
        return "not_run", None, "assets", "spec"
    bad = [
        a
        for a in assets
        if "drivaer" in str(a.get("source") or "").lower() and a.get("role") != "render_only"
    ]
    return ("fail" if bad else "pass"), bad or "ok", "render_only", "authoring/episode.spec.yaml"


def _beat_plan_coverage(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    path = ctx.lesson_dir / "authoring" / "beat-segments.yaml"
    if not path.is_file():
        return "not_run", None, "beat-segments.yaml", str(path)
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return "fail", str(exc), "readable beat-segments.yaml", str(path)
    beats = data.get("beats") or []
    if not beats:
        return "fail", 0, ">=1 beat", str(path)
    spec_claims = {
        claim.id for claim in getattr(ctx.spec, "claims", []) if getattr(claim, "status", "") == "must_teach"
    }
    plan_claims = {str(item) for beat in beats for item in (beat.get("claims") or [])}
    missing = sorted(spec_claims - plan_claims)
    six = {"question", "case", "mechanism", "derivation", "evidence", "conclusion"}
    types = {str(beat.get("type")) for beat in beats}
    missing_types = sorted(six - types)
    if missing or missing_types:
        return "fail", {"missing_claims": missing, "missing_types": missing_types}, "spec claims and six beat types", str(path)
    return "pass", len(beats), len(beats), str(path)


def _beat_coverage(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    beats = getattr(ctx.spec, "beats", None)
    claims = getattr(ctx.spec, "claims", None)
    if not beats or not claims:
        return "not_run", None, "beats and claims", "spec"
    required = {"question", "case", "mechanism", "derivation", "evidence", "conclusion"}
    present = {getattr(beat, "type", None) for beat in beats}
    missing_types = sorted(required - present)
    must_teach = {claim.id for claim in claims if getattr(claim, "status", "") == "must_teach"}
    used = {claim for beat in beats for claim in getattr(beat, "claims", [])}
    unused = sorted(must_teach - used)
    if missing_types or unused:
        return "fail", {"missing_types": missing_types, "unused_claims": unused}, "all six beat types, every must_teach claim used", "spec"
    return "pass", len(beats), len(beats), "spec"


def _timeline_assets(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    path = ctx.build_root / "contracts" / "timeline.spec.json"
    if not path.is_file():
        return "not_run", None, "timeline.spec.json", str(path)
    try:
        timeline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "fail", str(exc), "readable timeline", str(path)
    entries = list(timeline.get("video") or []) + list(timeline.get("audio") or [])
    if not entries:
        return "fail", 0, ">=1 timeline entry", str(path)
    missing = []
    for entry in entries:
        asset = entry.get("asset") or {}
        asset_path = asset.get("path")
        if not asset_path:
            missing.append(f"{entry.get('shot_id') or entry.get('role')}: no asset path")
            continue
        if not Path(asset_path).is_file():
            missing.append(asset_path)
    if missing:
        return "fail", missing, "every timeline asset exists", str(path)
    return "pass", len(entries), len(entries), str(path)


def _narration_measured(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    voice = getattr(ctx.spec, "voice", None)
    declared = voice.get("path") if isinstance(voice, dict) else None
    if declared:
        candidate = Path(str(declared))
        if not candidate.is_absolute():
            for base in (ctx.build_root.parent.parent, ctx.build_root):
                resolved = base / candidate
                if resolved.is_file():
                    candidate = resolved
                    break
        if not candidate.is_file():
            return "fail", str(declared), "voice.path exists", str(candidate)
    path = ctx.build_root / "narration" / "narration.resequenced.meta.json"
    if not path.is_file():
        path = ctx.build_root / "narration" / "narration.meta.json"
    if not path.is_file():
        return "not_run", None, "narration meta", str(path)
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        segments = meta.get("segments") or []
    except (OSError, ValueError) as exc:
        return "fail", str(exc), "readable narration.meta.json", str(path)
    if not segments:
        return "fail", 0, ">=1 narration segment", str(path)
    measured = max(float(segment.get("end_s") or 0) for segment in segments)
    lo = getattr(ctx.spec, "min_seconds", None)
    hi = getattr(ctx.spec, "max_seconds", None)
    if lo is None or hi is None:
        return "not_run", measured, "spec duration window", "spec"
    ok = lo <= measured <= hi
    return ("pass" if ok else "fail"), {"measured_s": round(measured, 3), "target_s": getattr(ctx.spec, "total_seconds", None)}, [lo, hi], str(path)


def _frames(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    candidates = [
        p
        for sub in ("scenes", "slides", "animation")
        for p in (ctx.build_root / sub).glob("*")
        if p.is_file()
    ]
    if not candidates:
        return "not_run", 0, ">=1 rendered frame/clip", str(ctx.build_root)
    return "pass", len(candidates), ">=1 rendered frame/clip", str(ctx.build_root)


def _subtitles(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    path = ctx.lesson_dir / "subtitles.srt"
    if not path.is_file():
        return "not_run", None, "subtitles.srt", str(path)
    return "pass", path.stat().st_size, ">0", str(path)


def _audio(ctx: EvalContext) -> tuple[Status, Any, Any, str]:
    path = ctx.build_root / "narration" / "narration.wav"
    if not path.is_file():
        return "not_run", None, "narration.wav", str(path)
    return "pass", path.stat().st_size, ">0", str(path)


AUTO_RULES: dict[str, Callable[[EvalContext], tuple[Status, Any, Any, str]]] = {
    "beat_coverage": _beat_coverage,
    "beat_plan_coverage": _beat_plan_coverage,
    "timeline_assets": _timeline_assets,
    "narration_measured": _narration_measured,
    "claim_source_coverage": _claim_source,
    "duration_window": _duration,
    "voice_decided": _voice,
    "rights_checked": _rights,
    "drivaer_render_only": _drivaer,
    "frames_present": _frames,
    "subtitles_present": _subtitles,
    "audio_present": _audio,
}

# News-side rules live next to their own contract (production/checks_news.py)
# and share this executor; the course rules above stay untouched.
from course_control.production.checks_news import NEWS_RULES  # noqa: E402

AUTO_RULES.update(NEWS_RULES)

# E1 display chain alignment (production/checks_display.py), same pattern.
from course_control.production.checks_display import DISPLAY_RULES  # noqa: E402

AUTO_RULES.update(DISPLAY_RULES)

# E6 deck design binding (production/checks_deck_design.py): plain pages fail.
from course_control.production.checks_deck_design import DECK_DESIGN_RULES  # noqa: E402

AUTO_RULES.update(DECK_DESIGN_RULES)


@dataclass
class CheckReport:
    lesson: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def auto_failed(self) -> list[CheckResult]:
        return [r for r in self.results if r.kind == "auto" and r.status == "fail"]

    @property
    def review_open(self) -> list[CheckResult]:
        return [r for r in self.results if r.kind == "review" and r.status == "review"]

    @property
    def not_run(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "not_run"]

    def as_dict(self, stage: str) -> dict:
        return {
            "schema_version": 1,
            "lesson": self.lesson,
            "stage": stage,
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "results": [r.as_dict() for r in self.results],
            "exceptions": [
                r.as_dict()
                for r in self.results
                if r.status in {"fail", "review", "not_run"}
            ],
        }


def run_checks(
    spec: Any,
    rubric: QualityRubric,
    lesson_dir: Path,
    build_root: Path,
    *,
    book_index: Path | None = None,
    only: set[str] | None = None,
) -> CheckReport:
    ctx = EvalContext(spec=spec, lesson_dir=lesson_dir, build_root=build_root, book_index=book_index)
    report = CheckReport(lesson=str(getattr(spec, "episode", "unknown")))
    for dimension in rubric.dimensions.values():
        for check in dimension.checks:
            if only is not None and check.id not in only:
                continue
            report.results.append(_run_one(check, ctx))
    return report


def _run_one(check: CheckSpec, ctx: EvalContext) -> CheckResult:
    if check.kind == "review":
        return CheckResult(
            id=check.id,
            kind="review",
            severity=check.severity,
            status="review",
            prompt=check.prompt,
        )
    fn = AUTO_RULES.get(check.rule or "")
    if fn is None:
        return CheckResult(
            id=check.id,
            kind="auto",
            severity=check.severity,
            status="fail",
            actual=None,
            expected=check.rule,
            detail=f"unknown auto rule: {check.rule}",
        )
    status, actual, expected, evidence = fn(ctx)
    return CheckResult(
        id=check.id,
        kind="auto",
        severity=check.severity,
        status=status,
        actual=actual,
        expected=expected,
        evidence=evidence,
    )
