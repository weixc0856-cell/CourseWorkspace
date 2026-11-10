"""Five-line quality report aggregator.

It reads artifacts produced by other stages and never infers a pass.  Each
dimension is reported independently; a missing check is ``INCOMPLETE`` and a
high-risk finding is ``BLOCKED``.  ``QUALITY_PASS`` requires every dimension to
be PASS or WARN, and ``RELEASE_APPROVED`` additionally requires a human release
approval file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .paths import LessonPaths

PASS = "PASS"
WARN = "WARN"
BLOCKED = "BLOCKED"
INCOMPLETE = "INCOMPLETE"

DIMENSIONS = (
    ("Q1", "内容可信度", "Content QA"),
    ("Q2", "教学有效性", "Teaching QA"),
    ("Q3", "视听体验", "Media QA"),
    ("Q4", "工程完整性", "Build QA"),
    ("Q5", "最终交付", "Release QA"),
)


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _q1(paths: LessonPaths) -> dict:
    from .review_decisions import summarize as summarize_decisions

    decisions = summarize_decisions(paths.build_root)
    if decisions["present"] and decisions["findings"]:
        counts = decisions["counts"]
        if decisions["unknown_decisions"]:
            return {
                "status": WARN,
                "reason": "decisions.json contains an unknown decision value",
                "evidence": ["build/<slug>/review/decisions.json"],
                "counts": counts,
                "needs_human_review": True,
            }
        if decisions["undecided"]:
            return {
                "status": WARN,
                "reason": f"{len(decisions['undecided'])} finding(s) have no decision",
                "evidence": ["build/<slug>/review/decisions.json"],
                "counts": counts,
                "needs_human_review": True,
            }
        if counts.get("accepted") or counts.get("deferred"):
            return {
                "status": WARN,
                "reason": (
                    f"adjudicated, but {counts.get('accepted', 0)} accepted and "
                    f"{counts.get('deferred', 0)} deferred finding(s) remain open"
                ),
                "evidence": ["build/<slug>/review/decisions.json"],
                "counts": counts,
                "needs_human_review": True,
            }
        return {
            "status": PASS,
            "reason": "every finding is rejected or fixed by a named reviewer",
            "evidence": ["build/<slug>/review/decisions.json"],
            "counts": counts,
            "needs_human_review": False,
        }
    cross = _load(paths.build_root / "review" / "review_cross.json")
    if cross is not None:
        summary = cross.get("summary") or {}
        return {
            "status": WARN,
            "reason": "independent A/B review; disputes and evidence gaps still need "
            "human adjudication",
            "evidence": [
                "build/<slug>/review/review_cross.json",
                "build/<slug>/review/claim_registry.json",
            ],
            "claims": summary.get("claims"),
            "disputed": summary.get("disputed"),
            "needs_human_review": summary.get("needs_human_review"),
            "missing_evidence": summary.get("missing_evidence"),
        }
    report = _load(paths.build_root / "review" / "review.json")
    claims = paths.lesson_dir / "authoring" / "claims.yaml"
    if report is None:
        return {
            "status": INCOMPLETE,
            "reason": "no ContentQA report under build/<slug>/review/review.json",
            "evidence": [],
        }
    status = str(report.get("status") or "")
    findings = report.get("findings") or []
    if status in {"blocked", "failed"}:
        return {
            "status": BLOCKED,
            "reason": f"ContentQA status={status}",
            "evidence": ["build/<slug>/review/review.json"],
            "findings": len(findings),
        }
    if status != "completed":
        return {
            "status": INCOMPLETE,
            "reason": f"ContentQA status={status}",
            "evidence": ["build/<slug>/review/review.json"],
        }
    return {
        "status": WARN,
        "reason": "single-model candidate findings; no Claim Registry or independent "
        "evidence verification",
        "evidence": ["build/<slug>/review/review.json"],
        "findings": len(findings),
        "claims_registry": claims.is_file(),
    }


def _q2(paths: LessonPaths) -> dict:
    teaching = _load(paths.build_root / "quality" / "teaching-qa.json")
    if teaching is not None:
        return {
            "status": str(teaching.get("status") or INCOMPLETE),
            "reason": str(teaching.get("summary") or "teaching report present"),
            "evidence": ["build/<slug>/quality/teaching-qa.json"],
        }
    narrative = _load(paths.build_root / "quality" / "narrative.json")
    if narrative is None:
        return {
            "status": INCOMPLETE,
            "reason": "no Teaching QA report and no narrative plan validation",
            "evidence": [],
        }
    status = str(narrative.get("status") or INCOMPLETE)
    mapped = {"pass": WARN, "warn": WARN, "fail": BLOCKED}.get(status, INCOMPLETE)
    return {
        "status": mapped,
        "reason": "narrative structure validated; teaching effectiveness still "
        "requires human or learner evidence",
        "evidence": ["build/<slug>/quality/narrative.json"],
    }


def _q3(paths: LessonPaths) -> dict:
    media = _load(paths.build_root / "quality" / "media-qc.json")
    mix = _load(paths.build_root / "audio" / "mix.json")
    if media is None:
        return {
            "status": INCOMPLETE,
            "reason": "no Media QA report; full-file audio/video/subtitle checks not run",
            "evidence": [],
        }
    status = str(media.get("status") or INCOMPLETE)
    evidence = ["build/<slug>/quality/media-qc.json"]
    reason = f"media checks: {status}"
    if mix is not None:
        evidence.append("build/<slug>/audio/mix.json")
        if mix.get("status") != "pass":
            if status == PASS:
                status = WARN
            reason += f"; BGM mix status={mix.get('status')}"
    elif any(cue for cue in (paths.lesson.audio.bgm or [])):
        if status == PASS:
            status = WARN
        reason += "; BGM is planned but no mix artifact exists"
    return {"status": status, "reason": reason, "evidence": evidence}


def _q4(paths: LessonPaths) -> dict:
    report = _load(paths.build_root / "final" / "build-report.json")
    if report is None:
        return {
            "status": INCOMPLETE,
            "reason": "no build-report.json",
            "evidence": [],
        }
    verdict = str(report.get("verdict") or "")
    stages = {stage.get("name"): stage.get("status") for stage in report.get("stages", [])}
    skipped = [name for name, status in stages.items() if status == "skipped"]
    if verdict == "fail":
        return {
            "status": BLOCKED,
            "reason": "build report verdict=fail",
            "evidence": ["build/<slug>/final/build-report.json"],
            "stages": stages,
        }
    status = PASS if not skipped else WARN
    return {
        "status": status,
        "reason": "build report verdict=pass" + (f"; skipped stages: {', '.join(skipped)}" if skipped else ""),
        "evidence": ["build/<slug>/final/build-report.json"],
        "stages": stages,
    }


def _q5(paths: LessonPaths) -> dict:
    build_root = paths.build_root
    subtitles_artifact = paths.subtitles_path()
    if (
        subtitles_artifact is None
        and paths.lesson.subtitles.enabled
        and paths.lesson.subtitles.mode == "word"
    ):
        subtitles_artifact = build_root / "subtitles.words.json"
    required = {
        "narration": build_root / "narration" / "narration.wav",
        "subtitles": subtitles_artifact,
        "build_report": build_root / "final" / "build-report.json",
        "media_qc": build_root / "quality" / "media-qc.json",
        "approval": paths.lesson_dir / "authoring" / "approval.json",
    }
    final = build_root / "final" / "course-video-mixed.mp4"
    if not final.is_file():
        final = build_root / "final" / "course-video.mp4"
    required["final_video"] = final
    missing = [name for name, path in required.items() if path is None or not path.is_file()]
    review = _load(build_root / "quality" / "review-approval.json")
    release = _load(build_root / "quality" / "release-approval.json")
    review_ok = bool(
        review
        and review.get("decision") == "approved"
        and str(review.get("approved_by") or "").strip()
    )
    release_ok = bool(
        release
        and release.get("decision") == "approved"
        and str(release.get("approved_by") or "").strip()
    )
    if missing:
        return {
            "status": BLOCKED,
            "reason": "missing release artifacts: " + ", ".join(missing),
            "evidence": [],
            "missing": missing,
        }
    if not review_ok:
        return {
            "status": WARN,
            "reason": "all release artifacts present; human review approval is pending",
            "evidence": ["build/<slug>/quality/review-approval.json"],
        }
    if not release_ok:
        return {
            "status": WARN,
            "reason": "human review approved; release sign-off is pending",
            "evidence": [
                "build/<slug>/quality/review-approval.json",
                "build/<slug>/quality/release-approval.json",
            ],
        }
    return {
        "status": PASS,
        "reason": "all release artifacts present, reviewed and release-approved",
        "evidence": [
            "build/<slug>/quality/review-approval.json",
            "build/<slug>/quality/release-approval.json",
        ],
    }


WARNING_CLASS = {
    # A warning that a human must read; it is not an automatic release veto.
    "Q1": "human_review",
    "Q2": "human_review",
    "Q3": "human_review",
    # Skipped stages and missing approvals block a release.
    "Q4": "blocking",
    "Q5": "blocking",
}


def _classify(dimensions: list[dict]) -> list[dict]:
    for item in dimensions:
        if item["status"] == WARN:
            item["warning_class"] = WARNING_CLASS.get(item["id"], "human_review")
        else:
            item["warning_class"] = None
    return dimensions


def build_quality_report(workspace: Path, paths: LessonPaths) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    dimensions = _classify(
        [
            {"id": "Q1", "name": "内容可信度", "engine": "Content QA", **_q1(paths)},
            {"id": "Q2", "name": "教学有效性", "engine": "Teaching QA", **_q2(paths)},
            {"id": "Q3", "name": "视听体验", "engine": "Media QA", **_q3(paths)},
            {"id": "Q4", "name": "工程完整性", "engine": "Build QA", **_q4(paths)},
            {"id": "Q5", "name": "最终交付", "engine": "Release QA", **_q5(paths)},
        ]
    )
    statuses = {item["status"] for item in dimensions}
    build_pass = dimensions[3]["status"] in {PASS, WARN}
    verify_fail = (not build_pass) or BLOCKED in statuses
    verify_incomplete = INCOMPLETE in statuses
    verify_pass = not verify_fail and not verify_incomplete
    verify_warn = verify_pass and WARN in statuses
    quality_verified = verify_pass and statuses == {PASS}
    needs_human_review = any(
        item.get("warning_class") == "human_review" for item in dimensions
    )
    blocking_warnings = [
        item["id"]
        for item in dimensions
        if item.get("warning_class") == "blocking"
    ]
    review_approval = _load(paths.build_root / "quality" / "review-approval.json")
    release_approval = _load(paths.build_root / "quality" / "release-approval.json")
    review_approved = bool(
        verify_pass
        and review_approval
        and review_approval.get("decision") == "approved"
        and str(review_approval.get("approved_by") or "").strip()
    )
    release_approved = bool(
        review_approved
        and release_approval
        and release_approval.get("decision") == "approved"
        and str(release_approval.get("approved_by") or "").strip()
    )

    report = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": _now(),
        "dimensions": dimensions,
        "states": {
            "BUILD_PASS": build_pass,
            "VERIFY_PASS": verify_pass,
            "VERIFY_WARN": verify_warn,
            "VERIFY_INCOMPLETE": verify_incomplete,
            "VERIFY_FAIL": verify_fail,
            # Legacy name kept for readers; it means "verified, warnings allowed".
            "QUALITY_PASS": verify_pass,
            "QUALITY_VERIFIED": quality_verified,
            "NEEDS_HUMAN_REVIEW": needs_human_review,
            "BLOCKED_WARNINGS": blocking_warnings,
            "REVIEW_APPROVED": review_approved,
            "RELEASE_APPROVED": release_approved,
        },
        "risks": [
            f"{item['id']} {item['name']}: {item['reason']}"
            for item in dimensions
            if item["status"] in {WARN, BLOCKED, INCOMPLETE}
        ],
    }
    target = paths.build_root / "quality" / "quality-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_markdown(report, target.with_suffix(".md"))
    _write_html(report, target.with_suffix(".html"))
    return report, target


def _write_markdown(report: dict, path: Path) -> None:
    lines = [
        f"# 课程质量报告：{report['lesson']}",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "| 维度 | 状态 | 说明 |",
        "| --- | --- | --- |",
    ]
    for item in report["dimensions"]:
        lines.append(f"| {item['id']} {item['name']} | {item['status']} | {item['reason']} |")
    lines += [
        "",
        "## 完成状态",
        "",
        f"- BUILD_PASS: {report['states']['BUILD_PASS']}",
        f"- QUALITY_PASS: {report['states']['QUALITY_PASS']}",
        f"- NEEDS_HUMAN_REVIEW: {report['states']['NEEDS_HUMAN_REVIEW']}",
        f"- BLOCKED_WARNINGS: {report['states']['BLOCKED_WARNINGS']}",
        f"- RELEASE_APPROVED: {report['states']['RELEASE_APPROVED']}",
        "",
        "## 风险",
        "",
    ]
    lines += [f"- {risk}" for risk in report["risks"]] or ["- 无"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(report: dict, path: Path) -> None:
    rows = "".join(
        f"<tr><td>{item['id']}</td><td>{item['name']}</td>"
        f"<td class=\"{item['status'].lower()}\">{item['status']}</td>"
        f"<td>{item['reason']}</td></tr>"
        for item in report["dimensions"]
    )
    risks = "".join(f"<li>{risk}</li>" for risk in report["risks"]) or "<li>无</li>"
    html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>课程质量报告：{report['lesson']}</title>
<style>
body{{font-family:system-ui,"Segoe UI",sans-serif;margin:2rem;color:#1f2328;background:#fbfaf7}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #d8d3ca;padding:.55rem .7rem;text-align:left;vertical-align:top}}
th{{background:#efece6}}
.pass{{color:#1a7f37;font-weight:600}}.warn{{color:#9a6700;font-weight:600}}
.blocked{{color:#b42318;font-weight:600}}.incomplete{{color:#57606a;font-weight:600}}
code{{background:#efece6;padding:.1rem .3rem;border-radius:4px}}
</style></head><body>
<h1>课程质量报告：{report['lesson']}</h1>
<p>生成时间：{report['generated_at']}</p>
<table><thead><tr><th>维度</th><th>名称</th><th>状态</th><th>说明</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>完成状态</h2>
<ul>
<li>BUILD_PASS: {report['states']['BUILD_PASS']}</li>
<li>QUALITY_PASS: {report['states']['QUALITY_PASS']}</li>
<li>NEEDS_HUMAN_REVIEW: {report['states']['NEEDS_HUMAN_REVIEW']}</li>
<li>BLOCKED_WARNINGS: {report['states']['BLOCKED_WARNINGS']}</li>
<li>RELEASE_APPROVED: {report['states']['RELEASE_APPROVED']}</li>
</ul>
<h2>风险</h2><ul>{risks}</ul>
<p>工程构建通过不等于课程质量合格；模型意见不能代替来源证据；发布必须由人批准。</p>
</body></html>"""
    path.write_text(html, encoding="utf-8")


__all__ = ["BLOCKED", "INCOMPLETE", "PASS", "WARN", "build_quality_report"]
