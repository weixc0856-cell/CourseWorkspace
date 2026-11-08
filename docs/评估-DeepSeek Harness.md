# 评估：DeepSeek Harness CLI 与本项目 Agent 分工（2026-11-07）

- **目的**：判断新安装的 DeepSeek Harness CLI 是否值得替换或补充 Claude Code，接入课程视频生产。
- **结论先行**：**不替换 Claude Code，不进入 CourseControl 运行时依赖**。dsh 可作为可选的独立第二代理，用于镜头代码的对照生成或独立复核；生产编排仍由 Claude Code + CourseControl 负责。
- **范围**：只测“按固定 SPEC 生成 8 秒 Code2Video 镜头代码”，不测整课编排、不测 TTS、不写入课程正文。

## 1. 环境与版本

| 项 | 值 |
| --- | --- |
| Claude Code | 2.1.319；经 cc-switch（`127.0.0.1:15721`）路由到 DeepSeek（显示名 DeepSeek-V4-flash） |
| DeepSeek Harness CLI | `@deepseek-ai/dsh@0.2.2-rc.1`，命令 `dsh` |
| dsh provider / model | `deepseek-official` / `deepseek-flash`（默认，符合“固定 flash、禁用 pro”） |
| Node / 渲染 | Node 24；Code2Video `capture.mjs`（Playwright + ffmpeg） |
| 日期 | 2026-11-07 |

### 凭据与权限（本机实测）

- dsh 需要 `DEEPSEEK_API_KEY`。本机已有系统级变量 `DeepSeek-API`，但 dsh **不会**自动读取该名字；启动时需显式导出，未写入任何文件：
  `DEEPSEEK_API_KEY="$(...Machine 'DeepSeek-API'...)" dsh headless ...`
- dsh 有 `read-only` / `workspace-write` / `danger-full-access` 预设，默认 `workspace-write` + 审批 `ask`。
- **Windows 上 `dsh-bash-sandbox` 被禁用**（配置里 `disabled: process.platform === 'win32'`）。因此 `workspace-write` 在 Windows 只是工具审批边界，不是 OS 级沙箱；不得把不可信任务交给它跑全权限命令。

## 2. 固定对比任务

同一份 `SPEC.md`（8.0 s、1920×1080、30 fps、Canvas 2D、固定文案、`window.READY` / `window.seek(t)` / `window.DUR`、确定性、无外部资源），只允许产出 `index.html` + `main.js`，不渲染、不写 VERIFY。

- 任务目录：`build/harness-compare/{dsh,claude}/`（`build/` 不入库）
- 两侧使用同一渲染器、同一 QC：
  `node CodeVideoStudio/skills/code-video/scripts/capture.mjs . --fps 30 --dur 8 --size 1920x1080 --out out/final.mp4`
  `code_video_qc.check_video(...)` + `contact_sheet(...)`

## 3. 结果

| 指标 | dsh headless | Claude Code `-p` |
| --- | --- | --- |
| 墙钟时间 | **294 s** | **184 s** |
| 步数 / 工具调用 | 15 步 / 14 次（read 4、edit 3、write 2、pwsh 2、glob 2、grep 1） | 5 次（Read 1、Write 2、Bash 2） |
| 非缓存输入 / 输出 token | 29,523 / 49,883 | 35,136 / 34,977（另缓存读 222,848） |
| 产出 | `index.html` 775 B；`main.js` 13.8 KB | `index.html` 798 B；`main.js` 8.6 KB |
| `node --check` | 通过 | 通过 |
| 渲染耗时（240 帧） | 51 s（约 200 ms/帧） | **14 s（约 49 ms/帧）** |
| 编码参数 | H.264 / yuv420p / 1920×1080 / 30 fps / 8.000 s / 无音轨 | 同左 |
| 机器 QC | pass；1 段 freeze warning（1.37–3.33 s） | pass；**0 warning** |
| 固定文案 | 全部出现 | 全部出现 |
| 视觉 | 网格+辉光+暗角，装饰性强；Q/K/V 前期偏暗；构图上重下空 | 扁平深色，层级清楚；构图上重下空；标题下划线贴近副标题 |
| 契约遵循 | `READY`/`seek`/`DUR` 正确，无 wall-clock/random | 同左 |

### 3.1 关键发现

1. **两者都能一次生成可渲染、可过 QC 的镜头代码**；单镜头尺度上 dsh 已具备可用性，不是玩具。
2. **Claude Code 更快、更省输出 token、渲染成本更低**（同一画质契约下 49 vs 200 ms/帧）。dsh 的装饰性绘制（径向渐变、暗角、阴影）显著增加逐帧成本。
3. **dsh 的工具粒度更细、步数更多**（15 步），但总墙钟更慢；它的 `--json` 事件适合程序化审计（tool_call/tool_result/usage 齐全）。
4. **Windows 安全边界不同**：dsh 的 shell 沙箱在 Windows 关闭，Claude Code 的权限模式仍是主要边界。两者都不应拿不可信输入直接跑全权限任务。
5. **dsh 的产品化能力**：profiles/plugins、session 持久化、headless JSON、permission presets；适合做“第二意见/独立复核”，不适合替代已有的课程编排与契约层。

### 3.2 成本（按 DeepSeek 官方价，2026-11-07）

官方价（元 / 百万 token，`deepseek-flash`）：缓存命中输入 0.02（空闲）/ 0.04（高峰）；缓存未命中输入 1 / 2；输出 4 / 8。本次运行在周末夜间，按空闲价计。

| 项 | dsh | Claude Code |
| --- | ---: | ---: |
| 非缓存输入 | 29,523 | 35,136 |
| 缓存命中输入 | 713,600 | 222,848 |
| 输出 | 49,883 | 34,977 |
| 合计计费 token | 793,006 | 292,961 |
| 估算费用（空闲价） | **¥0.243** | **¥0.180** |
| 估算费用（高峰价） | ¥0.487 | ¥0.359 |

- Claude Code 便宜约 **26%**：虽然非缓存输入略多，但输出与缓存读都明显更少。
- dsh 总 token 约为 Claude 的 **2.7 倍**，主要来自 15 步中反复带入的上下文。
- Claude Code 事件里的 `total_cost_usd`（本次 $1.16）是按 Anthropic 价目估算的，**不是** cc-switch/DeepSeek 的实际账单；以上表为准。
- 单镜头成本都在 **¥0.5 以内**；即使一门课 10 个镜头、每个返工 3 次，API 成本也只有几元。真正的成本是**墙钟时间、渲染时间和人工审片**，不是 token 费。

## 4. 决策

| 选项 | 决策 |
| --- | --- |
| 用 dsh 替换 Claude Code | **否**。更慢、输出更多、Windows 沙箱缺位；没有契约层能力。 |
| 把 dsh 写入 CourseControl 运行时 | **否**。课程生产不需要第二个 Agent 运行时。 |
| dsh 作为可选第二代理 | **是（人工按需）**。用于关键镜头的对照生成或独立 review；产物必须走同一 `SPEC.md` + `capture.mjs` + QC。 |
| 模型规则 | 保持 `deepseek-flash`；不启用任何 pro 变体。 |
| 凭据 | 只从系统环境变量注入进程，不落盘、不写 `.env`、不写日志。 |

## 5. 复现命令

```powershell
# dsh（进程内注入系统环境变量，不落盘）
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DeepSeek-API','Machine')
dsh headless --permission-mode workspace-write --json "<task>" > run.jsonl

# Claude Code（同一任务）
claude -p --permission-mode acceptEdits --allowedTools "Read Write Edit Glob Grep" --output-format stream-json --verbose "<task>" > run.jsonl

# 渲染与 QC
node CodeVideoStudio/skills/code-video/scripts/capture.mjs build/harness-compare/<side> --fps 30 --dur 8 --size 1920x1080 --out out/final.mp4
uv run --project CourseControl python -c "from course_control.code_video_qc import check_video; ..."
```

## 6. 后续（仅在有需求时）

- 若需要 dsh 参与，优先做 **只读 review**（`--permission-mode read-only`），不让它改课程文件。
- 若要做批量对照，再写 `scripts/harness-ab.ps1` 包装两侧命令；当前不引入。
- 本评估不改变 `docs/技术雷达-视频生产.md` 中视频项目的评分；dsh 是 Agent 运行时，不是视频引擎。
