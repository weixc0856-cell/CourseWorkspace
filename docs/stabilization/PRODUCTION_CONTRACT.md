# 生产契约收敛（Production Contract）

- 日期：2026-11-10
- 状态：已实现最小收敛；01/05/06 的迁移待真实构建验证
- 关联审计：`docs/audit/ARCHITECTURE_CONFLICTS.md` C-01
- 关联决策：D-032、D-035、D-065、D-066、D-071

---

## 1. 问题

同一门课存在六种表示：

| 表示 | 位置 | 现在的角色 |
| --- | --- | --- |
| `storyboard.yaml` | `lessons/<slug>/` | deck/scene 的人工输入；shots 模式被 synthetic 覆盖 |
| `production.yaml` | `lessons/<slug>/authoring/` | shots 模式的唯一输入 |
| `director_plan.json` | `build/<slug>/director/` | 导演规划视图；默认不进入 build |
| `beats.yaml` | `lessons/<slug>/authoring/` | 镜头内部动作与诊断 |
| `shots.json` | `build/<slug>/` | 规范化时间线（生成物） |
| `timeline.spec.json` | `build/<slug>/contracts/` | Remotion 消费的 V1 时间线 |

05 的四个数字是 1（storyboard）、3（导演计划）、27（节拍表镜头条目）、1（build）；01 是 5（storyboard）、12（导演计划）、5（build）；06 是 7（production）、7（beats）、7（build）。

## 2. 决策

### 2.1 两种模式，各自只有一个权威

| 模式 | 生产单元 | 权威 | 不作为权威 |
| --- | --- | --- | --- |
| `deck` / `scene` / `recording` | **Page** | `storyboard.yaml` | 导演计划、节拍表、`shots.json` 都是视图 |
| `shots` | **Shot** | `authoring/production.yaml` | `storyboard.yaml` 不参与；导演计划是视图 |

- 导演计划可以生成或修改单元，但不能成为第二套权威。
- 节拍表只描述 Page/Shot 内部的动作；它不是独立可重渲染单元。
- `shots.json` / `timeline.spec.json` 是生成物，不手工编辑。
- 不新增第七种生产计划。

### 2.2 导演计划如何进入 build

`build` 增加显式开关：

```powershell
course-control build --lesson <slug> --storyboard-source director
```

- 默认 `storyboard`（或 shots 模式的 production），行为不变。
- `director` 读取 `build/<slug>/director/storyboard.director.yaml`；文件缺失即失败，不回退到 storyboard。
- `--storyboard <path>` 仍然优先，用于临时 handoff。
- `producer-rebuild` 打印的命令应使用 `--storyboard-source director`，而不是手写路径。

### 2.3 只读审计

```powershell
course-control plan-audit --lesson <slug>
```

输出 `mode`、`authority`、各表示的计数与 `mismatches`。它不修改任何文件，不阻断构建；用于迁移前判断"哪几个数字不是同一粒度"。

06 的结果是 `authority=production.yaml`，各计数一致；05 是 `authority=storyboard.yaml`，beats=27、director=3 与 expected=1 不一致。

## 3. 现有实现与差距

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| shots 模式 synthetic storyboard | 已有 | `LessonPaths.load` 从 `production.yaml` 生成 `Storyboard`，build 与 collect 消费同一份 |
| deck/scene storyboard | 已有 | 默认路径；`--storyboard` 可覆盖 |
| `--storyboard-source director` | **本轮新增** | 显式选择导演计划，不改变默认 |
| `plan-audit` | **本轮新增** | 只读计数与权威报告 |
| 05 的 Page 权威 | 未完成 | 05 仍是 1 个 storyboard 镜头；导演计划 3 个、beats 27 个条目只是视图。文档不再声称"27 个独立镜头" |
| 01 的 Page 权威 | 未完成 | storyboard 5 个镜头；导演计划 12 个是视图。完整构建应使用 storyboard，或在迁移后使用 director |
| 06 的 Shot 权威 | 已完成 | production 7 = beats 7 = build 7；storyboard 文件为空，不参与 |

### 3.1 05 的迁移选择

两个选项，二选一，不要同时维护：

1. **保持 Page 权威**（推荐，成本低）：`attention_5min.py` 是一个 292 秒场景；节拍表 27 条是内部动作；producer 的 3 个镜头改为 1 个 `scene_base`，或明确标注为"章节视图"。
2. **拆成 3 个可独立渲染的 Manim 类**：每个类对应导演计划的一个镜头；producer 的增量重建才成立。成本是拆分 1,622 行场景与重跑渲染。

在没有拆分之前，`producer-affected` 报 3 个镜头、`render:manim` 整场景重渲，这是已知限制，不写成"镜头级增量"。

## 4. 兼容性与回滚

- `storyboard.yaml` 保留；shots 模式继续 synthetic，不要求作者写空文件。
- 默认 build 行为不变；只有显式 `--storyboard-source director` 才读导演计划。
- `plan-audit` 只读，可随时删除。
- 回滚：移除 `--storyboard-source` 参数即可回到 2026-11-10 之前的行为；不迁移任何课程资产。

## 5. 验收

1. `course-control plan-audit --lesson 06` 输出 `authority=production.yaml`、`mismatches: none`。
2. `course-control plan-audit --lesson 05` 明确列出 beats/director 的计数差异，且不阻断。
3. 对 06 跑 `build --storyboard-source director`（若导演计划存在）与默认 build，产物集合一致；不存在时明确失败。
4. 不新增第二种镜头定义；`storyboard.director.yaml` 只由导演计划生成，不手工维护。
