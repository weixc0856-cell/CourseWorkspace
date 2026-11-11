# ContentQA — 内容审查


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个知识板块（本机开发，不入库）；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
默认用 **Claude Code** 对课程内容做事实与一致性核查，产出**候选意见**；也可显式切到 OpenAI 兼容 API。它只读课程、只写 `build/<slug>/review/`，不影响课程构建的 verdict。

- 需求：`docs/PRD.md` FR-12
- 架构：`docs/ARCHITECTURE.md` §3.4、§4.3
- 配置模板：`config/content-qa.example.yaml`

## 裁决队列（2026-11-10）

审查意见本身不是结论。每条 finding 的处置写入 `build/<slug>/review/decisions.json`：

```powershell
uv run --project CourseControl course-control review-status --lesson <slug>
uv run --project CourseControl course-control review-decide --lesson <slug> --id <finding> --decision fixed --by <name>
```

`accepted` / `deferred` 保持开放；`rejected` 必须写理由；未裁决的 finding 一律进入人工复核。

## 边界

| 允许 | 不允许 |
| --- | --- |
| 读取 `slides.md`、`lecture_notes.md`、`sources.yaml` | 修改 `lessons/` 任何文件 |
| 写 `build/<slug>/review/review.json`、`review.md`、`raw/` | 写 `shots.json` 或 `build-report.json` |
| 写 `runtime/tasks/` 任务记录 | 启动、停止或切换本地模型 |
| 无凭据时标记 `blocked` | 静默降级到本地模型并声称完成同等核查 |

## 配置

```powershell
copy config\content-qa.example.yaml config\content-qa.yaml
```

- `backend: claude_code`（默认）：读取 `config/claude-code.yaml`；不可用时直接 `blocked`，不静默降级。
- `backend: api`：走 OpenAI 兼容接口，填写 `base_url` 与 `model`；API key 只从环境变量读取。

`config/content-qa.yaml` 已被忽略，凭据不得写进仓库。也可用 `--config <path>` 指定其他本机配置。任务记录写实际 `provider`（`claude_code` / `remote` / `local`），不得冒充。

`api_key_env` 可以填**任何已存在的环境变量名**，不需要新建一套凭据。例如 Windows 上已有 `DeepSeek-API`，直接写 `api_key_env: "DeepSeek-API"`；base_url 与模型名按供应商的 OpenAI 兼容接口填写（模型 id 可用 `GET /v1/models` 查询）。

上下文：默认 `context_limit: 16384`；长篇页面按段拆分。上限 65536，不允许把整门课塞进一次请求。

## 输出

```text
build/<slug>/review/
├── review.json   # 结构化报告：tasks[]、findings[]、errors[]
├── review.md     # 人工可读
└── raw/          # 模型返回非法 JSON 时的原始响应
```

单条意见的 `verdict`：`supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked`。
run 状态：`completed` / `blocked` / `failed`。退出码：0 / 3 / 1。

## 命令

```powershell
uv sync --project ContentQA
uv run --project ContentQA content-qa review --lesson 01-shell-for-ai-era
uv run --project ContentQA content-qa status --lesson 01-shell-for-ai-era
uv run --project ContentQA content-qa schema
.\.venv\Scripts\python -m unittest discover -s tests -t .   # 在 ContentQA/ 内
```

测试使用本地 mock 服务，不需要网络与真实凭据。

## 来源清单

`lessons/<slug>/sources.yaml`（可选，由作者维护）：

```yaml
sources:
  - id: S1
    title: "The Linux Command Line"
    path: "assets/sources/tlcl.pdf"
    excerpt: "可选短摘录，最多 800 字符进入提示词"
```

没有来源清单时，所有事实只能标记为 `needs_human_review` 或 `unsupported`。

## 本期不做

ASR、自动 TTS、公式符号验证、证据语料全文索引、模型 A/B 交叉审核。见 `docs/PRD.md` OPEN-05。
