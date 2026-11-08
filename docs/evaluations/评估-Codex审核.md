# 评估：用 Codex 审核 CourseWorkspace

日期：2026-11-08
结论：**可行，但只适合作为独立的第二意见，不适合作为唯一验收门禁。**

## 1. 定位

当前分工是 Claude Code 负责课程开发（代码、契约、文档、课程候选稿），Codex 只做审核：

```text
Claude Code 生产
   ↓
提交 / diff / 候选内容
   ↓
Codex 只读审核（独立模型、独立会话）
   ↓
人工复核 + 现有 check.ps1 / ContentQA / 来源证据
   ↓
合并 / 交付
```

Codex 不能修改课程正文、不能自动 apply、不能把“模型说通过”写成 `pass`。

## 2. 本地实测

环境：

- Codex CLI `0.167.0`，npm 安装，可执行。
- 当前 provider：`custom`，模型 `deepseek-v4-flash`，端点 `api.deepseek.com`。
- 不是本机 8080 模型；课程内容进入 Codex 就是发送到远程 DeepSeek。
- `codex login status` 显示未登录 OpenAI，但 custom provider 不依赖 OpenAI 登录。

实测结果：

| 测试 | 结果 |
| --- | --- |
| `codex exec -s read-only "Reply with exactly: OK"` | 返回 `OK`，退出码 0 |
| `codex exec --json` | JSONL 事件可读；该次 `input_tokens=19222`、`output_tokens=13` |
| `codex review --commit e82aba0` | 返回 P1/P2 两条具体发现，带文件/行号 |
| `codex exec` 审阅 `docs/动画渲染适配器.md` | 返回 5 条具体不一致，使用 143,049 tokens |
| `codex exec --output-schema ...` | 超过 10 分钟未完成，已停止；当前 custom provider 下不可用 |

### 2.1 真实 review 发现了什么

对 Motion Canvas 自动化提交 `e82aba0` 的审核返回：

- **P1**：`_verify` 只拒绝零时长，时长偏差只给 warning；截断 MP4 仍可能 `pass`。
- **P2**：Vite 未关闭 HMR，渲染时可能写回 `src/scenes/*.meta`，让构建修改输入。

这两条是真实问题；后续提交已经修正时长下限/半成品清理，并关闭了 headless HMR。这证明 Codex 能发现实质缺陷，但也说明它审的是**固定 SHA**，旧提交的结论不能直接套到新代码。

对适配器文档的纯文本审核又返回 5 条：

1. 文档声称所有 adapter 都校验分辨率/帧率/时长/帧数，实际 Manim/CodeVideo 没有统一做这些比较。
2. 文档把 Blender adapter 与独立 `scene-run` 验收混为一谈。
3. Motion 时长偏差超过 10% 仍只 warning，和文档“至少一项不通过即 fail”不一致。
4. 两次失败后，`_render_once` 若已创建部分 MP4，可能残留。
5. 缓存复用走 `_verify`，不校验帧数，和“帧数校验”表述不一致。

这 5 条中：第 4 条已修（失败即删除半成品）；第 1/2/3/5 条已按实际能力修正文档或收紧实现。说明 Codex 对**文档—代码一致性**也有实际价值，但会读很多文件，token 成本高。

## 3. 适用性判断

| 审核对象 | 适合度 | 原因 |
| --- | --- | --- |
| 流水线代码、契约、测试、脚本 | **高** | diff 明确，可复现，Codex 能读代码并给出文件/行号 |
| 文档与实现一致性 | **中高** | 本次实测有效；但会主动读大量文件，需限制范围 |
| 课程 slides / lecture notes 事实核查 | **中** | 只能给候选意见；必须提供来源摘录，最终由人/来源裁决 |
| 教学结构、节奏、视觉叙事 | **中低** | 模型可给建议，但缺少真实观看与课程目标判断 |
| 成片视频/画面审核 | **低** | 当前没有验证 Codex 的视频/多帧视觉能力；应继续用人工看片/contact sheet |
| 最终交付 verdict | **不适合** | 模型不具备证据链权威，且输出非确定；不能替代 `check.ps1`、ContentQA、人工验收 |

## 4. 推荐接入方式

### 4.1 代码审核（优先）

```powershell
codex review --base origin/main
# 或
codex review --commit <sha>
```

- 只读 sandbox。
- 每次记录被审 SHA、模型、provider、耗时、token。
- 结果保存到 `build/<slug>/review/codex/<sha>.md`（或 repo 外的审核目录），不进入交付 verdict。
- 人工把 P1/P2 逐条复核；确认后才改代码。
- 不加入 `check.ps1` 硬门禁；可作为 PR 前的可选步骤。

### 4.2 课程内容审核（需授权）

只有明确同意把课程内容发送到 DeepSeek 时才做：

```text
输入：单页 slides + 对应 lecture_notes + sources 摘录
输出：候选 findings（claim / evidence / severity / source_ref）
```

- 不要把整门课或整个 `lessons/` 递给 Codex。
- 不发 `.env`、`config/*.yaml`、模型权重。
- 结论只作候选；与 ContentQA、来源证据、人工判断并列。
- 建议先做 10 页小样本，统计“确认有效 / 误报 / 漏报”。

### 4.3 不建议的接入

- 不建议让 Codex 直接改课程或自动 apply。
- 不建议把 Codex 接入 `producer-run` 的硬门禁。
- 不建议依赖 `--output-schema`，当前实测会挂起；先用 `--json` + 提示词内 JSON + 本地解析。
- 不建议让 Codex 读取整个仓库：项目硬上限是 64K，但 Codex 本次文档审核用了 143K tokens；其 catalog 还允许 ~943K 自动压缩，直接违反项目规则。

## 5. 建议的 wrapper

如果要落地，建议独立脚本而不是改 CourseControl 主链：

```text
scripts/codex-review.ps1
  --mode code|content
  --base <branch> | --commit <sha> | --paths <files>
  --out build/<slug>/review/codex/<id>.md
  --timeout 600
```

要求：

- `-s read-only`，禁止写 workspace。
- `--ephemeral`，避免污染会话历史。
- `--cd` 指向只包含被审文件的临时目录/临时 worktree，防止它自行扩大读取范围。
- 记录 `model/provider/usage/thread_id`；过滤掉配置告警与 skill frontmatter 错误。
- 超时或 CLI 不可用 = `blocked`，不是 `pass`。
- 输出 Markdown findings；暂不做自动 verdict。
- 每次审核绑定 commit SHA 或文件 hash；旧结论不复用。

## 6. 风险与限制

1. **数据外发**：当前 Codex 使用 DeepSeek 远程 API。课程正文归用户所有，发送前必须获得明确授权；代码/公开文档可先做。
2. **上下文超标**：项目规则 64K，但 Codex 默认 catalog 支持 ~1M；本次文档审核实际用 143K。必须用临时目录/文件白名单限制，而不能只靠提示词。
3. **非确定性**：同一 SHA 两次审核可能给不同 findings；只能作第二意见。
4. **误报/漏报**：本次既有真实发现，也有需要人工确认的表述差异；不能直接当缺陷清单。
5. **可用性噪声**：本机 Codex 有 MCP 配置错误、旧 rollout 损坏、skill frontmatter 错误；wrapper 要过滤，不能把这些当审核结论。
6. **模型能力**：当前是 `deepseek-v4-flash`，不是 GPT/Claude；代码 review 表现可用，但不保证深度。
7. **工具执行**：`codex review` 会执行 git/PowerShell 读取命令；read-only 不写入，但仍有时延和输出噪声。
8. **结构化输出**：`--output-schema` 当前超时，不能作为主路径。

## 7. 分阶段建议

1. **Phase 1（推荐先做）**：只审代码/diff；人工复核；不接触 `lessons/`。
2. **Phase 2**：对公开文档和契约做一致性审核；固定 SHA、限制文件集。
3. **Phase 3**：经授权后做单页课程内容候选审核，统计误报率。
4. **Phase 4**：若稳定，作为 PR 可选审查步骤；仍不进入交付硬门禁。

## 8. 最终判断

- **代码审查：值得用。** 本次真实发现了时长校验、HMR 写入等实质问题。
- **课程内容审查：可以用，但只能是候选意见。** 必须解决数据授权、来源证据和 64K 上下文限制。
- **最终验收：不要用 Codex 替代。** 继续由 `check.ps1`、ContentQA、来源证据和人工验收负责。

一句话：**Claude Code 生产，Codex 做独立第二意见；Codex 不是验收人。**
