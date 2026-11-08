# 评估：Primer 式模拟视频 POC（30 秒）

日期：2026-11-08
参考：Primer《Simulating the Evolution of Rock, Paper, Scissors》（15:00，Godot 制作）
产物：`build/primer-poc/poc.mp4`（1920×1080 / 30 fps / 30 s）
产物（Three.js 版）：`build/primer-poc/poc-three.mp4`
端到端：`build/lesson-simulation/animation/primer-rps.mp4`（adapter capture + QC PASS）
导演计划：`build/lesson-simulation/director/director_plan.json`（1 镜头 / code_video / process_flow / ready）
源码：`BlenderStudio/scenes/primer-poc/`、`CodeVideoStudio/shots/primer-rps/`、`RemotionStudio/src/compositions/PrimerPoc.tsx`

## 1. 结论

**混合架构可行**：Python 模拟 + Blender Eevee + Remotion 排版，30 秒 POC 已跑通。  
**全 Blender 做 15 分钟不划算**：渲染时间与迭代成本会压过收益；长序列应交给 Three.js/CodeVideo 实时捕获，Blender 负责 hero 镜头与质感。

## 2. POC 内容

- 91 个 agent，六边形网格（半径 5），rock-paper-scissors 循环；
- 每帧 8 次局部更新，突变率 1e-4，固定 seed=7；
- Blender：六边形地块、按物种着色的 blob、对象颜色关键帧、慢速轨道相机、Eevee、720p；
- Remotion：三元状态图 + 轨迹、payoff 矩阵、mutation rate、衬线排版；世界视频放在右栏。

数据链路：

```text
simulation.spec.json
  → course-control simulation-run（SimulationData）
  → build/primer-poc/simulation.json（cells / frames_species / fractions）
  → world.py（Blender，900 帧 PNG）
  → ffmpeg（world.mp4）
  → PrimerPoc.tsx（Remotion，叠加三元图与表格）
  → poc.mp4
```

## 3. 实测

| 项 | 结果 |
| --- | --- |
| 模拟 | 91 cells × 900 帧，秒级 |
| Blender 世界 | 900 帧 / 720p30 / Eevee，约 12 分钟（~0.8 s/帧） |
| Three.js 世界 | 900 帧 / 720p30 / SwiftShader，**45.7 秒**（~51 ms/帧），快约 15.7× |
| Remotion 合成 | 900 帧 / 1080p30，约 1.5 分钟 |
| 成片 | 30.0 s / 1920×1080 / 30 fps / 4.7 MB |
| 确定性 | 同 seed 重跑得到同一组物种帧；Three.js 两次 capture 的 MP4 sha256 完全一致 |

Blender 5.2 当前构建没有 `file_format=FFMPEG` 枚举，POC 改为 PNG 序列 + ffmpeg 编码。

## 4. 能复用什么

- 模拟数据契约（cells + 每帧物种 + 比例）；
- `world.py` 的六边形地块、object color 关键帧、相机/灯光模板；
- Remotion 三元图、payoff 表、衬线排版；
- 版式/配色系统可直接约束 2×2 面板。

## 5. 不能直接复用什么

- 15 分钟长片的渲染：按 720p30 的 0.8 s/帧线性外推，1080p30 约 13 小时/遍，1440p60 约 20–40 小时/遍；返工成本高；
- 多面板同步：`PrimerQuad` 2×2 组件已实现并做过 still 验证；真实四 seed capture 与 30 s 成片尚未跑；
- 章节卡、音乐/音效、旁白：未做；
- Blender 没有 agent 点缓存导入：当前用 Python 生成对象颜色/位置关键帧，agent 上千时会膨胀。

## 6. 已确定的路线

`SimulationSpec` 已固化为 `CourseControl/src/course_control/simulation.py`；长序列引擎已决定用 Three.js/CodeVideoStudio，Blender 只做 hero 镜头，不引入 Godot。理由见 D-053。

1. `SimulationSpec` 契约（seed、网格、规则、帧数、每帧状态）已实现；
2. Blender 侧只保留 `world.py` 这类“数据 → 场景”任务，不直接在 Blender 里写模拟；
3. 长序列用 Three.js/CodeVideo 实时渲染（已接入 CodeVideo adapter：ShotSpec.inputs.simulation_spec → simulation.json → capture → QC PASS；导演层 `visual_kind: simulation` 自动路由），Blender 做特写/材质/灯光；
4. 2×2 面板、三元图、表格、字幕全部交给 Remotion；`PrimerQuad` 已给出布局；
5. 音频单独做，先解决授权音乐与中文旁白。

## 7. 边界

- 这是视觉 POC，不含旁白、音乐、字幕；
- 世界面板有轻微暗角和裁切，正式版需要重新构图；
- 地块颜色是 28% 物种色混合，正式版可做更细的dominance/高程；
- 没有接入导演/制片主链，是一次独立技术验证。
