"""Orchestration: scope -> privacy gate -> budget -> snapshot -> codex -> archive.

Exit codes
----------
0  review completed (findings may exist; this is never a production verdict)
1  contract/scope error
2  privacy gate or budget guard refused the run; codex was not called
3  codex execution failed or the review output is incomplete
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ai_runtime.budget import estimate_text_tokens

from . import archive
from .budget import BudgetPolicy, policy_for
from .executor import (
    CodexExecutor,
    CodexSettings,
    ExecutorError,
    ProviderInfo,
    RealCodexExecutor,
    provider_info,
    settings_for,
)
from .parser import FindingsParseError, extract_findings, parse_events
from .privacy import PrivacyDecision, decide
from .schema import (
    ExecutionInfo,
    ExecutionStatus,
    FileRecord,
    FindingsEnvelope,
    Manifest,
    PrivacyInfo,
    ReviewStatus,
    ReviewType,
    ScopeInfo,
    ScopeMode,
)
from .scope import (
    ScopeError,
    ScopeResolution,
    Snapshot,
    build_snapshot,
    resolve_repo_root,
    resolve_scope,
)
from .workspace_layout import content_root

EXIT_OK = 0
EXIT_CONTRACT = 1
EXIT_BLOCKED = 2
EXIT_EXECUTION = 3

FINDINGS_EXAMPLE = {
    "findings": [
        {
            "severity": "P1|P2|P3|INFO",
            "category": "Correctness|Reliability|Security|Documentation|Teaching",
            "file": "path/to/file.py",
            "line": 42,
            "problem": "what is wrong",
            "evidence": "concrete code or document evidence",
            "impact": "what breaks or is misleading",
            "suggested_fix": "smallest correct fix",
            "confidence": "high|medium|low",
            "verification": "unverified",
        }
    ]
}


@dataclass(frozen=True)
class RunOptions:
    review_type: ReviewType = ReviewType.code
    commit: str | None = None
    base: str | None = None
    files: tuple[str, ...] = ()
    context_files: tuple[str, ...] = ()
    workspace: Path = field(default_factory=Path.cwd)
    output_root: Path | None = None
    allow_external_content: bool = False
    timeout_s: int = 600
    isolated: bool = True
    dry_run: bool = False
    now: datetime | None = None
    provider_override: ProviderInfo | None = None


@dataclass
class RunOutcome:
    exit_code: int
    review_dir: Path | None
    manifest: Manifest | None
    message: str


def _iso_now(moment: datetime | None = None) -> str:
    value = moment or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _review_dir(
    output_root: Path,
    review_type: ReviewType,
    review_rev: str,
    moment: datetime,
) -> Path:
    day = moment.strftime("%Y-%m-%d")
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:4]
    name = f"{review_type.value}-{review_rev[:7]}-{stamp}-{suffix}"
    return output_root / day / name


def _scope_info(
    resolution: ScopeResolution,
    *,
    changed: int = 0,
    reviewed: int = 0,
) -> ScopeInfo:
    return ScopeInfo(
        mode=resolution.mode,
        commit=resolution.commit,
        base=resolution.base,
        head_sha=resolution.head_sha,
        review_rev=resolution.review_rev,
        diff_range=resolution.diff_range,
        worktree_dirty=resolution.worktree_dirty,
        dirty_paths=resolution.dirty_paths,
        changed_files=changed,
        reviewed_files=reviewed,
    )


def build_task_prompt(
    resolution: ScopeResolution,
    snapshot: Snapshot,
) -> str:
    rev_label = (
        f"commit {resolution.commit}"
        if resolution.mode is ScopeMode.commit
        else f"base {resolution.base} (merge-base {resolution.base_resolved})"
    )
    file_lines = []
    for blob in snapshot.files:
        role = "变更文件" if blob.role == "changed_file" else "上下文文件"
        file_lines.append(f"- {blob.path}（{role}，{blob.size} bytes）")
    if not file_lines:
        file_lines.append("- （本次只有删除或二进制变更，见 diff.patch）")

    lines = [
        "# 独立代码审核任务（只读）",
        "",
        "你是 CourseWorkspace 的独立第二意见审核者。你不能修改任何文件，"
        "你的结论不是生产验收结论，也不会改变任何验收状态。",
        "",
        "## 审核快照",
        f"- 范围：{rev_label}",
        f"- 差异：{resolution.diff_range}",
        f"- 工作树是否有未提交改动：{'是' if resolution.worktree_dirty else '否'}"
        "（审核内容全部来自 Git 对象，与工作树无关）",
        "",
        "## 输入",
        "- 本次审核的完整补丁与文件全文已直接附在本消息中，不需要读取任何目录。",
        "- 不要执行 shell 命令，不要联网，不要写入、创建或删除任何文件。",
        "- 如果仍然执行命令，只允许只读查看，并且不得离开本次提供的材料范围。",
        "",
        "## 硬性约束",
        "1. 只依据本消息中提供的补丁与文件全文；严禁读取未提供的文件。",
        "2. 严禁联网，严禁执行会修改文件的命令，严禁写入、创建或删除任何文件。",
        "3. 只报告由本次变更引入或暴露的真实缺陷：正确性、可靠性、安全、"
        "文档与实现不一致。",
        "4. 不要复述改动，不要给泛泛的工程建议，不要编造证据或行号。",
        "5. 每条发现必须给出具体文件、尽可能准确的行号、可核对的证据和影响。",
        "6. 没有发现时返回空数组；不要为了凑数制造问题。",
        "7. 不要输出 verdict、pass/fail、分数或生产结论。",
        "",
        "## 审核文件",
        *file_lines,
        "",
        "## 输出格式",
        "最终消息必须是 Markdown，并包含且只包含一个如下形式的 findings 代码块：",
        "",
        "```json:findings",
        json.dumps(FINDINGS_EXAMPLE, ensure_ascii=False, indent=2),
        "```",
        "",
        "- severity：P1 必须修复，P2 应该修复，P3 次要，INFO 提示。",
        "- category：Correctness / Reliability / Security / Documentation / Teaching。",
        "- confidence：high / medium / low，表示你对该发现的把握，不是事实证明。",
        "- verification 固定写 unverified；任何发现都需要人工复核。",
        "- findings 数组可以为空。",
        "",
        "## 变更补丁（完整）",
        "",
        "```diff",
        snapshot.diff_text.rstrip(),
        "```",
        "",
        "## 变更与上下文文件全文",
        "",
    ]
    if not snapshot.files:
        lines.append("（本次没有可附带的文本文件；请只依据上方的补丁。）")
    for blob in snapshot.files:
        lines.extend(
            [
                f"### {blob.path}",
                "",
                "```",
                _decode(blob.data).rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _decode(data: bytes) -> str:
    return (data or b"").decode("utf-8", "replace")


def _write_input(
    review_dir: Path,
    snapshot: Snapshot,
    prompt: str,
) -> tuple[Path, list[FileRecord]]:
    input_dir = review_dir / "input"
    records: list[FileRecord] = []

    diff_bytes = snapshot.diff_text.encode("utf-8")
    archive.write_bytes(input_dir / "diff.patch", diff_bytes)
    records.append(
        FileRecord(
            path="diff.patch",
            role="diff",
            sha256=archive.sha256_bytes(diff_bytes),
            bytes=len(diff_bytes),
            tokens_estimated=estimate_text_tokens(snapshot.diff_text),
            source="generated",
        )
    )

    for blob in snapshot.files:
        archive.write_bytes(input_dir / blob.path, blob.data)
        records.append(
            FileRecord(
                path=blob.path,
                role="context" if blob.role == "context" else "changed_file",
                sha256=blob.sha256,
                bytes=blob.size,
                tokens_estimated=estimate_text_tokens(_decode(blob.data)),
                source="git_object",
            )
        )

    prompt_bytes = prompt.encode("utf-8")
    archive.write_text(input_dir / "REVIEW_TASK.md", prompt)
    records.append(
        FileRecord(
            path="REVIEW_TASK.md",
            role="task_prompt",
            sha256=archive.sha256_bytes(prompt_bytes),
            bytes=len(prompt_bytes),
            tokens_estimated=estimate_text_tokens(prompt),
            source="generated",
        )
    )

    listing = ["role\tsha256\tbytes\ttokens_estimated\tpath"]
    for record in records:
        listing.append(
            f"{record.role}\t{record.sha256}\t{record.bytes}\t"
            f"{record.tokens_estimated}\t{record.path}"
        )
    archive.write_text(review_dir / "input-files.txt", "\n".join(listing) + "\n")
    return input_dir, records


def _redacted_argv(argv: list[str], prompt: str) -> list[str]:
    redacted = list(argv)
    for index, value in enumerate(redacted):
        if value == prompt:
            redacted[index] = f"<prompt:{len(prompt)} chars>"
    return redacted


def _execution_log(
    *,
    argv: list[str],
    prompt: str,
    result,
    stderr: str,
) -> str:
    lines = [
        f"started_at: {result.started_at}",
        f"finished_at: {result.finished_at}",
        f"duration_ms: {result.duration_ms}",
        f"exit_code: {result.exit_code}",
        f"timed_out: {result.timed_out}",
        f"argv: {json.dumps(_redacted_argv(argv, prompt), ensure_ascii=False)}",
        "",
        "--- stderr ---",
        stderr[-20000:],
        "",
    ]
    return "\n".join(lines)


def _finish(
    review_dir: Path,
    manifest: Manifest,
    exit_code: int,
    message: str,
) -> RunOutcome:
    manifest.artifacts = {
        "manifest": "manifest.json",
        "input_list": "input-files.txt",
    }
    if (review_dir / "input" / "diff.patch").exists():
        manifest.artifacts["diff"] = "input/diff.patch"
    if (review_dir / "events.jsonl").exists():
        manifest.artifacts["events"] = "events.jsonl"
    if (review_dir / "review.md").exists():
        manifest.artifacts["review"] = "review.md"
    if (review_dir / "execution.log").exists():
        manifest.artifacts["execution_log"] = "execution.log"
    if (review_dir / "findings.json").exists():
        manifest.artifacts["findings"] = "findings.json"
    if (review_dir / "input.sha256").exists():
        manifest.artifacts["input_hashes"] = "input.sha256"
    archive.write_manifest(review_dir, manifest)
    return RunOutcome(
        exit_code=exit_code,
        review_dir=review_dir,
        manifest=manifest,
        message=message,
    )


def run_review(
    options: RunOptions,
    *,
    executor: CodexExecutor | None = None,
    policy: BudgetPolicy | None = None,
) -> RunOutcome:
    moment = options.now or datetime.now(timezone.utc)

    # ---- contract / scope resolution (no archive on failure) -------------
    try:
        if options.review_type is ReviewType.code:
            if bool(options.commit) == bool(options.base):
                raise ScopeError("code review requires exactly one of --commit or --base")
            if options.files:
                raise ScopeError(
                    "code review does not take --files; use --context for extra files"
                )
        repo = resolve_repo_root(options.workspace)
        mode = ScopeMode.commit if options.commit else ScopeMode.base
        resolution = resolve_scope(
            repo,
            mode=mode,
            commit=options.commit,
            base=options.base,
        )
    except ScopeError as exc:
        return RunOutcome(EXIT_CONTRACT, None, None, str(exc))

    content = content_root(repo)
    output_root = options.output_root or (content / "build" / "reviews")
    review_dir = _review_dir(output_root, options.review_type, resolution.review_rev, moment)
    review_dir.mkdir(parents=True, exist_ok=True)
    try:
        review_id = review_dir.relative_to(content).as_posix()
    except ValueError:
        review_id = review_dir.as_posix()

    if executor is None:
        settings = settings_for(repo, isolated=options.isolated)
        executor = RealCodexExecutor(settings)
    else:
        settings = getattr(executor, "settings", None) or settings_for(
            repo, isolated=options.isolated
        )
    info = options.provider_override or provider_info(settings)
    privacy: PrivacyDecision = decide(
        options.review_type,
        allow_external_content=options.allow_external_content,
        host=info.endpoint_host,
        explicit_files=options.files,
    )

    manifest = Manifest(
        review_id=review_id,
        review_type=options.review_type,
        created_at=_iso_now(moment),
        workspace=str(repo),
        scope=_scope_info(resolution),
        privacy=PrivacyInfo(
            external_content=privacy.external_content,
            authorization=privacy.authorization,
            granted=privacy.allowed,
            provider=info.provider,
            model=info.model,
            endpoint_host=info.endpoint_host,
            notes=list(privacy.notes),
        ),
        execution=ExecutionInfo(
            executable=settings.executable,
            sandbox=settings.sandbox,
            isolation="isolated" if settings.isolated else "user-config",
            timeout_s=options.timeout_s,
        ),
    )

    if not privacy.allowed:
        manifest.flags.append("PRIVACY_BLOCKED")
        manifest.blocked_reason = privacy.reason
        return _finish(
            review_dir,
            manifest,
            EXIT_BLOCKED,
            privacy.reason or "privacy gate blocked the run",
        )

    if options.review_type is not ReviewType.code:
        manifest.flags.append("NOT_IMPLEMENTED")
        manifest.blocked_reason = (
            "phase 1 implements code review only; docs/course review execution "
            "is not implemented"
        )
        return _finish(
            review_dir,
            manifest,
            EXIT_CONTRACT,
            manifest.blocked_reason,
        )

    # ---- snapshot --------------------------------------------------------
    try:
        snapshot = build_snapshot(resolution, context_files=options.context_files)
    except ScopeError as exc:
        manifest.flags.append("SCOPE_REJECTED")
        manifest.blocked_reason = str(exc)
        return _finish(review_dir, manifest, EXIT_CONTRACT, str(exc))

    manifest.scope = _scope_info(
        resolution,
        changed=len(snapshot.changed),
        reviewed=len(snapshot.reviewed_paths),
    )
    manifest.exclusions = list(snapshot.exclusions)

    for blob in snapshot.files:
        if blob.path in ("diff.patch", "REVIEW_TASK.md"):
            manifest.flags.append("SCOPE_REJECTED")
            manifest.blocked_reason = (
                f"snapshot path collides with a generated artifact: {blob.path}"
            )
            return _finish(review_dir, manifest, EXIT_CONTRACT, manifest.blocked_reason)

    prompt = build_task_prompt(resolution, snapshot)

    # ---- budget guard ----------------------------------------------------
    diff_tokens = estimate_text_tokens(snapshot.diff_text)
    file_tokens = sum(
        estimate_text_tokens(_decode(blob.data)) for blob in snapshot.files
    )
    prompt_tokens = estimate_text_tokens(prompt)
    policy = policy or policy_for(isolated=settings.isolated)
    budget = policy.evaluate(
        diff_tokens=diff_tokens,
        file_tokens=file_tokens,
        task_prompt_tokens=prompt_tokens,
    )
    manifest.budget = budget
    if budget.warning:
        manifest.flags.append("BUDGET_WARNING")
    if budget.blocked:
        manifest.flags.append("BUDGET_BLOCKED")
        manifest.blocked_reason = budget.blocked_reason
        return _finish(
            review_dir,
            manifest,
            EXIT_BLOCKED,
            budget.blocked_reason or "budget guard blocked the run",
        )

    # ---- immutable input snapshot ---------------------------------------
    input_dir, records = _write_input(review_dir, snapshot, prompt)
    manifest.files = records
    archive.write_text(
        review_dir / "input.sha256",
        archive.hash_lines(archive.hash_directory(input_dir)),
    )

    if options.dry_run:
        manifest.flags.append("DRY_RUN")
        return _finish(
            review_dir,
            manifest,
            EXIT_OK,
            "dry run: snapshot and budget prepared; codex was not called",
        )

    # ---- execute ---------------------------------------------------------
    # The Codex working root must stay outside the repository: a directory
    # inside it lets Codex discover the repository and explore beyond scope.
    try:
        with tempfile.TemporaryDirectory(prefix="review-runner-") as temp:
            temp_dir = Path(temp)
            (temp_dir / "REVIEW_TASK.md").write_text(prompt, encoding="utf-8")
            before_temp = archive.hash_directory(temp_dir)
            result = executor.run(prompt, temp_dir, options.timeout_s)
            after_temp = archive.hash_directory(temp_dir)
            snapshot_intact = before_temp == after_temp
    except ExecutorError as exc:
        manifest.execution.launcher_error = str(exc)
        manifest.execution_status = ExecutionStatus.failed
        manifest.review_status = ReviewStatus.not_run
        manifest.flags.append("LAUNCH_FAILED")
        archive.write_text(review_dir / "execution.log", f"launcher error: {exc}\n")
        return _finish(review_dir, manifest, EXIT_EXECUTION, str(exc))

    manifest.execution.started_at = result.started_at
    manifest.execution.finished_at = result.finished_at
    manifest.execution.duration_ms = result.duration_ms
    manifest.execution.exit_code = result.exit_code
    manifest.execution.timed_out = result.timed_out
    manifest.execution.stdout_bytes = len(result.stdout.encode("utf-8"))
    manifest.execution.argv = _redacted_argv(result.argv, prompt)
    manifest.execution.stderr_tail = result.stderr[-4000:]
    manifest.execution.launcher_error = result.launcher_error
    archive.write_text(review_dir / "events.jsonl", result.stdout or "")
    archive.write_text(
        review_dir / "execution.log",
        _execution_log(
            argv=result.argv,
            prompt=prompt,
            result=result,
            stderr=result.stderr,
        ),
    )
    if result.timed_out:
        manifest.flags.append("TIMEOUT")

    parsed = parse_events(result.stdout or "")
    manifest.execution.thread_id = parsed.thread_id
    manifest.execution.noise_filtered = len(parsed.noise)
    manifest.execution.errors = parsed.errors[:20]

    intact = snapshot_intact
    manifest.execution.snapshot_intact = intact
    if not intact:
        manifest.flags.append("SNAPSHOT_MUTATED")

    if manifest.budget is not None:
        manifest.budget = policy.check_actual(manifest.budget, parsed.usage)
        if manifest.budget.violation:
            manifest.flags.append("BUDGET_VIOLATION")
        if manifest.budget.output_over_reserve:
            manifest.flags.append("OUTPUT_OVER_RESERVE")

    execution_ok = (
        result.exit_code == 0
        and not result.timed_out
        and result.launcher_error is None
        and intact
    )
    manifest.execution_status = (
        ExecutionStatus.success if execution_ok else ExecutionStatus.failed
    )

    message = parsed.last_agent_message
    archive.write_text(
        review_dir / "review.md",
        message
        if message
        else "# Review Report\n\n(no final agent message received)\n",
    )

    findings_saved = False
    if message:
        try:
            envelope: FindingsEnvelope = extract_findings(message)
        except FindingsParseError as exc:
            manifest.execution.errors.append(str(exc))
        else:
            archive.write_findings(review_dir, envelope)
            manifest.findings_count = len(envelope.findings)
            findings_saved = True

    review_ok = (
        execution_ok
        and parsed.jsonl_complete
        and findings_saved
        and not (manifest.budget and manifest.budget.violation)
    )
    if not execution_ok:
        manifest.review_status = ReviewStatus.not_run
    elif review_ok:
        manifest.review_status = ReviewStatus.completed
    else:
        manifest.review_status = ReviewStatus.incomplete

    if review_ok:
        return _finish(
            review_dir,
            manifest,
            EXIT_OK,
            f"review completed with {manifest.findings_count or 0} findings",
        )

    reasons = []
    if not execution_ok:
        reasons.append("codex execution failed")
    if not parsed.jsonl_complete:
        reasons.append("JSONL stream incomplete or contained non-noise errors")
    if not findings_saved:
        reasons.append("findings block missing or invalid")
    if manifest.budget and manifest.budget.violation:
        reasons.append("actual usage exceeded the 64K hard limit")
    return _finish(
        review_dir,
        manifest,
        EXIT_EXECUTION,
        "; ".join(reasons) or "review incomplete",
    )


__all__ = [
    "EXIT_BLOCKED",
    "EXIT_CONTRACT",
    "EXIT_EXECUTION",
    "EXIT_OK",
    "FINDINGS_EXAMPLE",
    "RunOptions",
    "RunOutcome",
    "build_task_prompt",
    "run_review",
]
