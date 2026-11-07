from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from ai_runtime import ContextBudget, ContextOverflow, TaskRecord, TaskStore
from ai_runtime.tasks import now as task_now

from .client import OnlineClient, OnlineError
from .config import ReviewConfig, load_config, resolve_api_key
from .contracts import Finding, ModelReply, ReviewReport, ReviewTask
from .splitter import Chunk, plan_chunks, pair_pages

SYSTEM_PROMPT = """你是课程内容审查助手。你的输出只是候选意见，不是最终结论。

任务：对给定的一页幻灯片与讲师手册块，找出可核查的论断，并判断是否有来源支持。

规则：
1. 只输出 JSON 对象，不要输出解释性文字。
2. 每条意见包含：slide（页码，整数）、claim（被核查的论断）、verdict、rationale（理由）、source_refs（来源 id 列表）。
3. verdict 只能是：supported（有来源支持）、unsupported（找不到支持）、disputed（来源冲突）、needs_human_review（无法判定）、not_checked（未核查）。
4. 不确定时使用 needs_human_review，禁止编造来源。source_refs 只能引用下方列出的来源 id。
5. 每页最多 8 条意见；没有可核查论断时返回 {{"findings": []}}。

输出格式：{{"findings": [{{"slide": 1, "claim": "...", "verdict": "...", "rationale": "...", "source_refs": []}}]}}

可用来源：
{sources}
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _load_sources(lesson_dir: Path, name: str) -> list[dict]:
    path = lesson_dir / name
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    entries = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict) and entry.get("id")]


def _source_index(sources: list[dict]) -> str:
    if not sources:
        return "（无来源清单；所有事实只能标记为 needs_human_review 或 unsupported）"
    lines = []
    for source in sources:
        line = f"- {source['id']}: {source.get('title', '')}"
        if source.get("path"):
            line += f" ({source['path']})"
        excerpt = str(source.get("excerpt", "")).strip()
        if excerpt:
            line += f"\n  摘录：{excerpt[:800]}"
        lines.append(line)
    return "\n".join(lines)


def _messages(chunk: Chunk, sources_text: str) -> list[dict]:
    system = SYSTEM_PROMPT.format(sources=sources_text)
    user = (
        f"页码：{chunk.slide}\n\n"
        f"幻灯片内容：\n{chunk.slide_text}\n\n"
        f"讲师手册内容：\n{chunk.notes_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _write_markdown(path: Path, report: ReviewReport) -> None:
    lines = [
        f"# 在线内容审查 · {report.lesson}",
        "",
        f"- 状态：`{report.status}`",
        f"- 模型：`{report.model}`",
        f"- 时间：{report.generated_at}",
        f"- 意见数：{len(report.findings)}",
        "",
    ]
    if report.errors:
        lines.extend(["## 错误", ""])
        lines.extend(f"- {error}" for error in report.errors)
        lines.append("")
    current = None
    for finding in sorted(report.findings, key=lambda item: (item.slide, item.claim)):
        if finding.slide != current:
            current = finding.slide
            lines.extend([f"## Slide {current}", ""])
        refs = f" 来源：{', '.join(finding.source_refs)}" if finding.source_refs else ""
        lines.append(f"- **[{finding.verdict}]** {finding.claim}")
        if finding.rationale:
            lines.append(f"  - 理由：{finding.rationale}{refs}")
        elif refs:
            lines.append(f"  -{refs}")
    if not report.findings:
        lines.extend(["（没有产生意见）", ""])
    _atomic_write(path, "\n".join(lines).rstrip() + "\n")


def _blocked(
    lesson: str, lesson_dir: Path, config: ReviewConfig | None, message: str
) -> ReviewReport:
    return ReviewReport(
        lesson=lesson,
        generated_at=_now(),
        model=config.model.model if config else "",
        base_url=config.model.base_url if config else "",
        status="blocked",
        tasks=[],
        findings=[],
        errors=[message],
    )


def run_review(
    workspace: Path,
    lesson_dir: Path,
    *,
    config_path: Path | None = None,
    client_factory=None,
) -> tuple[ReviewReport, Path]:
    """Review one lesson with the online model. Read-only with respect to content."""
    workspace = workspace.resolve()
    lesson_dir = lesson_dir.resolve()
    lesson = lesson_dir.name
    review_dir = workspace / "build" / lesson / "review"
    report_path = review_dir / "review.json"

    config = load_config(config_path)
    if config is None:
        report = _blocked(
            lesson,
            lesson_dir,
            None,
            "online model is not configured: create config/content-qa.yaml from the example",
        )
        _finish(report, report_path)
        return report, report_path

    if config.backend == "claude_code":
        cc = config.claude_code
        if cc is None or not cc.enabled or not cc.available():
            detail = (
                "claude-code is not configured"
                if cc is None or not cc.enabled
                else f"claude executable not found: {cc.executable}"
            )
            report = _blocked(lesson, lesson_dir, config, detail)
            _finish(report, report_path)
            return report, report_path
        api_key = None
    else:
        api_key = resolve_api_key(config)
        if not api_key:
            report = _blocked(
                lesson,
                lesson_dir,
                config,
                f"missing credentials: set environment variable {config.model.api_key_env}",
            )
            _finish(report, report_path)
            return report, report_path

    slides_path = lesson_dir / "slides.md"
    notes_path = lesson_dir / "lecture_notes.md"
    if not slides_path.is_file() or not notes_path.is_file():
        report = _blocked(
            lesson, lesson_dir, config, f"lesson files not found under {lesson_dir}"
        )
        _finish(report, report_path)
        return report, report_path

    pages = pair_pages(
        slides_path.read_text(encoding="utf-8"),
        notes_path.read_text(encoding="utf-8"),
    )
    chunks = plan_chunks(pages)
    sources_text = _source_index(_load_sources(lesson_dir, config.sources_file))

    client = (client_factory or (lambda: OnlineClient(config, api_key)))()
    store = TaskStore(workspace / "runtime" / "tasks")
    raw_dir = review_dir / "raw"
    budget = ContextBudget(
        limit=config.context_limit, reserved_output=config.model.max_tokens
    )

    tasks: list[ReviewTask] = []
    findings: list[Finding] = []
    errors: list[str] = []

    for chunk in chunks:
        task_id = f"contentqa-{lesson}-{chunk.task_id}"
        messages = _messages(chunk, sources_text)
        try:
            budget_report = budget.check(messages)
        except ContextOverflow as exc:
            tasks.append(
                ReviewTask(
                    task_id=task_id, slide=chunk.slide, status="failed", error=str(exc)
                )
            )
            errors.append(f"{chunk.task_id}: {exc}")
            continue

        record = TaskRecord(
            task_id=task_id,
            task_type="contentqa.review",
            assigned_model=config.model.model,
            status="running",
            input_artifacts=["slides.md", "lecture_notes.md"],
            output_artifacts=["build/<lesson>/review/review.json"],
            context_budget=budget_report.as_dict(),
            timeout_s=config.model.timeout_s,
        )
        record.started_at = task_now()
        store.save(record)
        try:
            reply, usage = client.chat_json(messages)
            model_reply = ModelReply.model_validate(reply)
        except (OnlineError, ValueError) as exc:
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            record.finished_at = task_now()
            store.save(record)
            raw = getattr(client, "last_raw", "")
            if raw:
                _atomic_write(raw_dir / f"{chunk.task_id}.txt", raw)
            tasks.append(
                ReviewTask(
                    task_id=task_id,
                    slide=chunk.slide,
                    status="failed",
                    estimated_input_tokens=budget_report.estimated,
                    error=record.error,
                )
            )
            errors.append(f"{chunk.task_id}: {record.error}")
            continue

        record.status = "completed"
        record.finished_at = task_now()
        record.context_budget.update({"usage": usage})
        store.save(record)
        tasks.append(
            ReviewTask(
                task_id=task_id,
                slide=chunk.slide,
                status="completed",
                estimated_input_tokens=budget_report.estimated,
            )
        )
        for finding in model_reply.findings:
            if finding.slide != chunk.slide:
                finding.slide = chunk.slide
            findings.append(finding)

    status = "failed" if any(task.status == "failed" for task in tasks) else "completed"
    report = ReviewReport(
        lesson=lesson,
        generated_at=_now(),
        model=config.model.model,
        base_url=config.model.base_url,
        status=status,
        tasks=tasks,
        findings=findings,
        errors=errors,
    )
    _finish(report, report_path)
    return report, report_path


def _finish(report: ReviewReport, report_path: Path) -> None:
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _atomic_write(report_path, payload)
    _write_markdown(report_path.with_name("review.md"), report)


def load_report(workspace: Path, lesson: str) -> ReviewReport | None:
    path = workspace / "build" / lesson / "review" / "review.json"
    if not path.is_file():
        return None
    return ReviewReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
