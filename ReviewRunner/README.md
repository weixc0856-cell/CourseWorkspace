# ReviewRunner


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个领域方案；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
独立的只读第二意见审核工具。它不属于课程生产主链：不修改任何源文件、不参与
`check.ps1` 验收、不输出生产 verdict。

Phase 1 只实现 **代码审查**（固定 commit 或 base 区间）。Docs/Course 已保留隐私门与
接口，但执行阶段返回 `NOT_IMPLEMENTED`。

## 命令

```powershell
# 审核一个固定提交
.\scripts\review.ps1 -Type Code -Commit ed53c2b

# 审核 base 区间（merge-base(base, HEAD)..HEAD）
.\scripts\review.ps1 -Type Code -Base origin/main

# 只准备快照与预算，不调用 Codex
.\scripts\review.ps1 -Type Code -Commit ed53c2b -DryRun

# 额外上下文文件（必须在该 revision 中已跟踪）
.\scripts\review.ps1 -Type Code -Commit ed53c2b -Context CourseControl/src/course_control/cli.py
```

等价的 Python 入口：

```powershell
uv run --project ReviewRunner review-runner run --type code --commit ed53c2b
```

## 安全边界

- 审核内容全部来自 Git 对象（`git diff` / `git cat-file`），不读工作树，避免“审的
  SHA 与实际内容不一致”。
- 补丁与文件全文直接内联到审核提示词，经 **stdin** 传给 Codex（Windows 命令行有
  32K 限制）；Codex 的 `-C` 指向仓库外的系统临时目录，不指向仓库根目录，避免 Git
  仓库发现与越界探索。归档副本仍写在 `build/reviews/.../input/`。
- 默认 `--ignore-user-config`：本机 MCP 服务器与插件不加载；provider 由项目
  `config/model-routing.yaml` 提供 `base_url/model/api_key_env`，**key 只从环境变量读取**，
  不写入 argv、日志或 manifest。
- 排除 `lessons/`、`build/`、`runtime/`、`config/`、`.env*`、密钥、模型权重与媒体文件。
- Course 审核默认禁止外发；必须逐次 `-AllowExternalContent`。Docs 必须显式 `-Files`。
- 运行前后校验临时工作目录的 SHA256；目录内容被修改即判定执行失败。

## 预算

| 项 | 值 |
| --- | ---: |
| 项目硬上限 | 65,536 |
| 安全余量 | 1,000 |
| 系统预留（隔离模式） | 18,000 |
| 系统预留（用户配置模式） | 24,000 |
| 指令 / 输出预留 | 3,000 / 8,000 |
| 文件内容预算（隔离模式） | 35,536 |

实测基线（2026-11-08，codex-cli 0.167.0，DeepSeek）：隔离模式 14,243 input tokens；
用户配置模式 19,238 tokens。估算使用 `ai_runtime.estimate_text_tokens`，只是近似；
运行后从 `turn.completed.usage` 读取实际用量。

- **输入**超过 64K → `BUDGET_VIOLATION`，审核不得为 `REVIEW_COMPLETED`。
- **输出**超过 8K 预留 → `OUTPUT_OVER_RESERVE` 告警，只作为成本信号，不否定审核。
- 实际审核实测（`ed53c2b`）：input 49,976、output 61,814、耗时 322 s；输入未超限，
  输出超预留，按上述规则告警。`turn.completed.usage` 是多步累计值，不直接等于单次
  请求上下文。

## 状态与退出码

| 轴 | 值 |
| --- | --- |
| execution_status | `NOT_RUN` / `EXECUTION_SUCCESS` / `EXECUTION_FAILED` |
| review_status | `NOT_RUN` / `REVIEW_COMPLETED` / `REVIEW_INCOMPLETE` |

| 退出码 | 含义 |
| ---: | --- |
| 0 | 审核完成（可有 findings；0 条也不等于代码正确） |
| 1 | 参数、路径或契约错误；Docs/Course 尚未实现 |
| 2 | 隐私门或预算守卫拒绝，未调用 Codex |
| 3 | Codex 执行失败或输出不完整 |

## 产物

```text
build/reviews/<date>/<type>-<sha7>-<timestamp>-<rand>/
  manifest.json        # 范围、文件哈希、隐私、预算、执行、双状态
  input-files.txt      # 白名单文件清单（role/sha256/bytes/tokens）
  input/               # Codex 唯一可见目录
    diff.patch
    REVIEW_TASK.md
    <repo-relative files>
  input.sha256         # 执行前快照哈希
  events.jsonl         # Codex --json 原始事件
  review.md            # Codex 最终消息原文
  execution.log        # argv（提示词已替换）、stderr、退出码、耗时
  findings.json        # 仅解析成功时写入
```

`findings.json` 没有 verdict，只有 `production_effect: none`；所有 finding 的
`verification` 强制为 `unverified`，必须人工复核后才能进入修复流程。

## 测试

```powershell
uv run --project ReviewRunner python -m unittest discover -s ReviewRunner/tests -t ReviewRunner
```

30 个测试全部使用 `FakeCodexExecutor`，不消耗外部 token。真实 Codex 集成测试单独执行：

```powershell
.\scripts\review.ps1 -Type Code -Commit <sha>
```

## 已知限制

- Windows 下 Codex 的 `read-only` 沙箱隔离强度未验证；本工具靠临时目录 + 前后哈希，
  不声称绝对沙箱隔离。
- 宿主 `~/.agents/skills` 的 skill 告警仍会出现，已作为噪声过滤并计数。
- 不使用 `--output-schema`（本机实测挂起）。
- 提示词内联全部材料并通过 stdin 传入，因此单次请求的估算上下文必须留在 64K 内；
  `turn.completed.usage` 是多步工具调用的累计值，不等同于单次请求上下文。
- Phase 1 不实现 Docs/Course 执行，不接 Producer 硬门禁，不自动 apply。
