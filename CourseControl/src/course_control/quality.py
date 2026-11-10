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
    approval = _load(build_root / "quality" / "release-approval.json")
    approved = bool(
        approval
        and approval.get("decision") == "approved"
        and str(approval.get("approved_by") or "").strip()
    )
    if missing:
        return {
            "status": BLOCKED,
            "reason": "missing release artifacts: " + ", ".join(missing),
            "evidence": [],
            "missing": missing,
        }
    if not approved:
        return {
            "status": WARN,
            "reason": "all release artifacts present; human release approval is pending",
            "evidence": ["build/<slug>/quality/release-approval.json"],
        }
    return {
        "status": PASS,
        "reason": "all release artifacts present and approved",
        "evidence": ["build/<slug>/quality/release-approval.json"],
    }


def build_quality_report(workspace: Path, paths: LessonPaths) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    dimensions = [
        {"id": "Q1", "name": "内容可信度", "engine": "Content QA", **_q1(paths)},
        {"id": "Q2", "name": "教学有效性", "engine": "Teaching QA", **_q2(paths)},
        {"id": "Q3", "name": "视听体验", "engine": "Media QA", **_q3(paths)},
        {"id": "Q4", "name": "工程完整性", "engine": "Build QA", **_q4(paths)},
        {"id": "Q5", "name": "最终交付", "engine": "Release QA", **_q5(paths)},
    ]
    statuses = {item["status"] for item in dimensions}
    build_pass = dimensions[3]["status"] in {PASS, WARN}
    quality_pass = build_pass and statuses <= {PASS, WARN}
    release_approval = _load(paths.build_root / "quality" / "release-approval.json")
    release_approved = bool(
        quality_pass
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
            "QUALITY_PASS": quality_pass,
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
<li>RELEASE_APPROVED: {report['states']['RELEASE_APPROVED']}</li>
</ul>
<h2>风险</h2><ul>{risks}</ul>
<p>工程构建通过不等于课程质量合格；模型意见不能代替来源证据；发布必须由人批准。</p>
</body></html>"""
    path.write_text(html, encoding="utf-8")


__all__ = ["BLOCKED", "INCOMPLETE", "PASS", "WARN", "build_quality_report"]
