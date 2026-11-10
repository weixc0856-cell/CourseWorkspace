# 任务执行标准（TASK_EXECUTION_STANDARD）

- 日期：2026-11-10
- 关联：C-19、C-20、C-21、C-30；`checkpoint.py`、`build_lock.py`、`timeouts.py`、`utils.py`
- 状态：已实现；检查点有单元测试，真实长片中断注入待执行

## 1. 阶段顺序

```text
config → validate → capture_slides → render:{motion_canvas,manim,blender,code_video}
       → collect → compose → [burn_subtitles] → [brand] → verify
```

- `config` 解析配置并写快照；blocking 冲突直接停止，不进入渲染。
- `validate` 每次都运行，不缓存。
- 引擎阶段只运行 `lesson.engines` 中声明且被镜头使用的引擎。
- `verify` 每次都运行，不复用检查点。

## 2. 状态

| 状态 | 含义 |
| --- | --- |
| `pass` | 阶段产物通过自身检查 |
| `fail` | 阶段失败；下游标记 `not_run` |
| `skipped` | 用户显式跳过（`--skip-render` / `--skip-compose`） |
| `not_run` | 上游失败导致未执行 |
| `not_applicable` | 该课程不使用此阶段 |

`build-report.verdict`：任一 `fail` → `fail`；任一 `skipped`/`not_run` → `incomplete`；其余 `pass`。SKIP 不等于 PASS。

## 3. 检查点

每个可复用阶段写 `build/<slug>/runtime/checkpoints/<stage>.json`：

```json
{
  "stage": "render:manim",
  "status": "pass",
  "config_fingerprint": "…",
  "inputs": {"lessons/demo/lesson.yaml": "sha256", "…": "sha256"},
  "outputs": {"animation/scene.mp4": "sha256"},
  "warnings": ["…"],
  "run_id": "20261110T101500Z-1a2b3c4d",
  "created_at": "2026-11-10T10:15:00+08:00"
}
```

复用条件全部满足才跳过：

1. 状态是 `pass`；跳过/不适用状态不复用。
2. `config_fingerprint` 相同（配置、跳过开关、storyboard 选择、镜头过滤）。
3. 每个输入文件的 SHA-256 相同。
4. 每个输出文件存在且 SHA-256 相同。

任一不满足就重跑该阶段；原因写入 `runtime/last-run.json` 的 `resume.invalid`。

## 4. Resume

```powershell
course-control build --lesson <slug> --resume
course-control build --lesson <slug> --resume-from compose
```

- `--resume`：复用所有有效检查点。
- `--resume-from <stage>`：复用该阶段之前的检查点；该阶段及其后强制重跑。
- `collect` 的检查点单独处理：它没有 `StageOutcome` 之外的返回值，复用后从固定路径读取 `shots.json`。
- 新的 resume 运行有新的 `run_id`；原运行记录不覆盖。`build-report` 写入 `resumed=true` 与 `reused_stages[]`。
- 不是"标记完成就跳过"：输出被删、被改、配置变化都会重跑。

## 5. 超时

`timeouts.py` 按阶段与课程时长解析，`config/tools.yaml` 可覆盖：

```yaml
timeouts:
  compose: 7200
  render:blender: 3600
```

| 阶段 | 默认 | 随目标时长缩放 |
| --- | ---: | --- |
| `capture_slides` | 600 s | 否 |
| `render:manim` | 1800 s | 否 |
| `render:blender` | 1900 s | 否 |
| `render:code_video` | 1800 s | ×2 |
| `compose` | 1800 s | ×3 |
| `burn_subtitles` | 900 s | ×1.5 |
| `brand` | 1800 s | ×1 |

超时行为：`run_command` 用 `taskkill /T` 杀进程树，返回 exit 124；阶段记录 `TIMEOUT after N seconds`。超时后可以 `--resume` 重跑该阶段；不会自动无限重试。

## 6. 并发与写入

- 同一课程同一时间只允许一个 build：`runtime/locks/build-<slug>.lock`。陈旧锁按 PID 回收。
- 不同课程可以并行；它们写各自的 `build/<slug>/`。
- 报告、检查点、配置快照、质量报告、mix/manifest 使用原子写（临时文件 + fsync + `os.replace`）。
- 进程被终止后，最多留下 `.tmp` 文件；不会留下半个 JSON。

## 7. 运行记录

`build/<slug>/runtime/last-run.json`：

```json
{
  "run_id": "…",
  "config_fingerprint": "…",
  "resume": {"enabled": true, "from": "compose", "reused": ["render:manim"], "replayed": ["compose"], "invalid": {}},
  "verdict": "pass"
}
```

它是"这次运行发生了什么"的唯一入口；`build-report.json` 是产物与检查的权威。
