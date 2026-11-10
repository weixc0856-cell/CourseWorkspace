# 配置标准（CONFIGURATION_STANDARD）

- 日期：2026-11-10
- 关联：C-24、C-29、C-08；`CourseControl/src/course_control/config_resolve.py`
- 状态：已实现；05/06/01/nvda 已实跑

## 1. 权威顺序

一次构建只解析一次配置，顺序固定：

1. `lessons/<slug>/lesson.yaml`：生产行为的课程权威（模式、时长、字幕声明、引擎）。
2. `config/*.yaml`：本机工具与后端配置（Blender/FFmpeg 路径、BGM 根目录、模型路由、ContentQA、Claude Code）。
3. 环境变量：只用于凭据存在性判断，**不读取值、不写入快照**。

导演、Producer、Renderer、QC 不得各自重新读取一套配置。它们读取同一份 `config-resolution.json`（或由同一次 `resolve_config` 产生的报告）。

## 2. 继承关系

```text
config/tools.yaml             工具路径、阶段超时
config/local-paths.yaml       TTS / BGM / AI 根目录
config/model-routing.yaml     远程 provider 与回退条件
config/content-qa.yaml        ContentQA 后端
config/authoring.yaml         文本生产后端
config/claude-code.yaml       Claude Code 模型与端点
        │
        ▼
lessons/<slug>/lesson.yaml    课程级覆盖（时长、字幕、引擎、BGM 策略）
        │
        ▼
build/<slug>/logs/config-resolution.json   本次运行的不可变快照
```

课程级配置不能覆盖工具路径；远程 provider 不能覆盖"本地优先、显式回退"。

## 3. 快照内容

`config-resolution.json` 每条记录：

| 字段 | 含义 |
| --- | --- |
| `key` | 点分键，例如 `duration.target_seconds` |
| `value` | 最终生效值 |
| `source` | 来源文件或 `environment` |
| `note` | 覆盖说明；密钥只记"存在/不存在" |

其它字段：

- `sources[]`：每个配置文件的路径、是否存在、SHA-256。
- `duration`：target / min / max / measured / timeline / authority。
- `conflicts[]`：`blocking` 阻断构建；非 blocking 进入 warning。
- `warnings[]`：不阻断但必须展示的解释。
- `fingerprint`：sources 与 values 的 SHA-256，用于 resume 判断配置是否变化。

## 4. 已实现的冲突检查

| 检查 | 条件 | 级别 |
| --- | --- | --- |
| `subtitle_language_mismatch` | 声明双语但 SRT 只有一种语言；或声明单语但 SRT 含两种 | blocking |
| `bgm_policy_violation` | `formal_course` / `news` 声明了 BGM cue | blocking |
| `deepseek_model_pinned` | provider=deepseek 且 model/vision_model 不是 `deepseek-flash` | blocking |
| `duration_outside_policy` | 实测旁白超出 min/max | blocking |
| 目标时长偏差 | 实测与 target 相差超过 `acceptance.duration_tolerance_seconds` | warning（实测权威，D-032） |
| 时间线与实测偏差 | 相差超过 0.5 s | warning |
| `measured` 但缺 `narration.meta.json` | 旁白启用且 timing=measured | warning |

## 5. 命令

```powershell
# 只解析并打印；不写文件
uv run --project CourseControl course-control config-resolve --lesson 05-transformer-5min

# 写 build/<slug>/logs/config-resolution.json
uv run --project CourseControl course-control config-resolve --lesson 05-transformer-5min --write

# build 每次都会写快照，并在 build-report 记录 config_fingerprint
uv run --project CourseControl course-control build --lesson 05-transformer-5min
```

## 6. 已知边界

- `lesson.yaml` 的 `duration.target_seconds` 是计划值；一旦有实测旁白，`duration.authority=measured`。
- 05 的四个数字现在有唯一解释：target 293（计划）、measured 292.38（权威）、timeline 292.37（生成物）、beats 286.08（内部动作视图）。
- 环境变量值永远不进入快照、日志或报告。密钥只在进程内读取。
- 新增配置项必须同时更新本文件与 `test_config_resolve.py`；否则视为第二套配置源。
