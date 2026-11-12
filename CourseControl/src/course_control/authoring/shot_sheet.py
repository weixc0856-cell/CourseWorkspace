"""Shot Sheet: the human design authority, compiled into a reviewable plan.

Since 2026-11-12 the shot sheet is ``storyboard.yaml`` at ``schema_version: 2``
-- not a second file.  That keeps the rule the code already enforced: one
authority per compose mode.  The v2 fields are all optional, so a v1
storyboard loads and builds exactly as before.

This module does three things, in one place so ``validate`` and the
``shot-sheet`` command can never disagree:

* resolve every reference a shot declares (continuity, assets, evidence);
* fingerprint each shot from its design fields, so an unchanged shot keeps its
  identity across compiles (P4 locks will diff these);
* compile the sheet into ``build/<slug>/shot-sheet/plan.json`` plus a
  human-readable ``review.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import ShotSpec, Storyboard
from ..paths import LessonPaths, path_problem

EVIDENCE_ID = r"^[A-Za-z0-9][^\s]{0,127}$"

# Rule ids used by ``validators``; kept here so both callers agree.
RULE_CONTINUITY = "V-45"
RULE_ASSET = "V-46"
RULE_EVIDENCE = "V-47"


def asset_path(paths: LessonPaths, ref: str) -> Path | None:
    """Resolve an asset ref against the lesson directory, then its assets dir."""
    if path_problem(ref):
        return None
    candidates = [(paths.lesson_dir / ref).resolve()]
    assets = paths.lesson.content.assets
    if assets:
        asset_dir = (paths.lesson_dir / assets).resolve()
        candidates.append((asset_dir / ref).resolve())
    return next((item for item in candidates if item.is_file()), None)


def _asset_entries(paths: LessonPaths, shot: ShotSpec) -> list[dict]:
    entries = []
    for ref in shot.asset_refs:
        resolved = asset_path(paths, ref)
        entries.append(
            {
                "ref": ref,
                "path": None if resolved is None else str(resolved),
                "sha256": _sha(resolved) if resolved is not None else None,
                "found": resolved is not None,
            }
        )
    return entries


def fingerprint(paths: LessonPaths, shot: ShotSpec) -> str:
    """Identity of one shot's design: its sheet fields plus its assets' bytes."""
    payload = {
        "id": shot.id,
        "slide": shot.slide,
        "engine": shot.engine,
        "scene": shot.scene,
        "cue_seconds": shot.cue_seconds,
        "sheet": shot.sheet_fields(),
        "assets": [
            [entry["ref"], entry["sha256"]] for entry in _asset_entries(paths, shot)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def issues(paths: LessonPaths) -> list[dict]:
    """Every problem the sheet can name precisely, as rule/level/message."""
    sheet = paths.storyboard
    found: list[dict] = []
    known = {item.id for item in sheet.continuity}
    assets_dir = (paths.lesson_dir / paths.lesson.content.assets).resolve() if paths.lesson.content.assets else None
    for shot in sheet.shots:
        for ref in shot.continuity_refs:
            if ref not in known:
                found.append(
                    {
                        "rule": RULE_CONTINUITY,
                        "level": "error",
                        "shot_id": shot.id,
                        "message": f"continuity ref '{ref}' is not declared in continuity",
                    }
                )
        for ref in shot.asset_refs:
            if asset_path(paths, ref) is not None:
                continue
            problem = path_problem(ref)
            if problem:
                detail = problem
            else:
                looked = paths.lesson_dir if assets_dir is None else f"{paths.lesson_dir} / {assets_dir}"
                detail = f"not found under {looked}"
            found.append(
                {
                    "rule": RULE_ASSET,
                    "level": "error",
                    "shot_id": shot.id,
                    "message": f"asset '{ref}': {detail}",
                }
            )
        for ref in shot.evidence_refs:
            if not re.match(EVIDENCE_ID, ref):
                found.append(
                    {
                        "rule": RULE_EVIDENCE,
                        "level": "error",
                        "shot_id": shot.id,
                        "message": f"evidence ref '{ref}' is not a valid id",
                    }
                )
    return found


def compile_sheet(paths: LessonPaths) -> dict:
    sheet: Storyboard = paths.storyboard
    shots = []
    for shot in sheet.shots:
        shots.append(
            {
                "id": shot.id,
                "slide": shot.slide,
                "engine": shot.engine,
                "scene": shot.scene,
                "cue_seconds": shot.cue_seconds,
                "fingerprint": fingerprint(paths, shot),
                **shot.sheet_fields(),
                "assets": _asset_entries(paths, shot),
            }
        )

    usage: dict[str, list[str]] = {item.id: [] for item in sheet.continuity}
    for shot in sheet.shots:
        for ref in shot.continuity_refs:
            usage.setdefault(ref, []).append(shot.id)

    source = paths.content_path(paths.lesson.content.storyboard)
    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "path": paths.lesson.content.storyboard,
            "sha256": _sha(source),
            "schema_version": sheet.schema_version,
        },
        "shots": shots,
        "continuity": [
            {
                "id": item.id,
                "label": item.label,
                "note": item.note,
                "shots": usage.get(item.id, []),
            }
            for item in sheet.continuity
        ],
        "summary": {
            "shots": len(sheet.shots),
            "designed": sum(1 for shot in sheet.shots if shot.is_sheet),
            "continuity_objects": len(sheet.continuity),
            "unused_continuity": sorted(
                item.id for item in sheet.continuity if not usage.get(item.id)
            ),
            "with_assets": sum(1 for shot in sheet.shots if shot.asset_refs),
            "with_evidence": sum(1 for shot in sheet.shots if shot.evidence_refs),
        },
        "issues": issues(paths),
    }


def review_markdown(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        f"# Shot Sheet 复核 — {plan['lesson']}",
        "",
        f"- 生成时间：{plan['generated_at']}",
        f"- 来源：`{plan['source']['path']}`（schema v{plan['source']['schema_version']}，"
        f"sha256 `{(plan['source']['sha256'] or '')[:12]}…`）",
        f"- 镜头 {summary['shots']}，其中有设计字段 {summary['designed']}；"
        f"连续性对象 {summary['continuity_objects']}；带资产 {summary['with_assets']}，"
        f"带证据 {summary['with_evidence']}",
        "",
        "## 镜头",
        "",
        "| # | 镜头 | 页 | 目的 | 连续性 | 资产 | 证据 | 转场 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, shot in enumerate(plan["shots"], start=1):
        transition = shot["transition"]
        transition_text = "-" if not transition else f'{transition["in"]}/{transition["out"]}'
        lines.append(
            "| {n} | `{id}` | {slide} | {purpose} | {cont} | {assets} | {evidence} | {trans} |".format(
                n=index,
                id=shot["id"],
                slide=shot["slide"],
                purpose=shot["purpose"] or "-",
                cont=", ".join(shot["continuity_refs"]) or "-",
                assets=", ".join(shot["asset_refs"]) or "-",
                evidence=", ".join(shot["evidence_refs"]) or "-",
                trans=transition_text,
            )
        )
    lines += ["", "## 连续性", ""]
    if plan["continuity"]:
        lines += ["| 对象 | 名称 | 出现镜头 |", "| --- | --- | --- |"]
        for item in plan["continuity"]:
            shots = ", ".join(item["shots"]) or "（未使用）"
            lines.append(f"| `{item['id']}` | {item['label']} | {shots} |")
    else:
        lines.append("（storyboard 未声明 continuity）")

    lines += ["", "## 问题", ""]
    if plan["issues"]:
        for issue in plan["issues"]:
            target = f" `{issue['shot_id']}`" if issue.get("shot_id") else ""
            lines.append(f"- [{issue['rule']}] {issue['level']}{target}: {issue['message']}")
    else:
        lines.append("无。")
    return "\n".join(lines) + "\n"


def write(paths: LessonPaths, plan: dict) -> dict[str, Path]:
    out = paths.build_root / "shot-sheet"
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "plan.json"
    review_path = out / "review.md"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    review_path.write_text(review_markdown(plan), encoding="utf-8")
    return {"plan": plan_path, "review": review_path}


def _sha(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
