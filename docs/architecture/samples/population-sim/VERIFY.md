# Sample 3 · 验证结果

## 渲染命令
```powershell
$env:NODE_PATH="$PWD/CodeVideoStudio/shots/compute-topology/node_modules"
node CodeVideoStudio/skills/code-video/scripts/capture.mjs `
  docs/architecture/samples/population-sim --fps 30 --dur 12 --size 1920x1080 `
  --out $PWD/build/architecture-samples/population-sim.mp4
```

## 机器结果（2026-11-10 实跑）
| 项 | 结果 |
|---|---|
| 文件 | `build/architecture-samples/population-sim.mp4` |
| 时长 | 12.000 s |
| 分辨率 / 帧率 | 1920×1080 / 30 fps |
| 编码 / 像素格式 | H.264 / yuv420p |
| SHA-256 前 16 位 | `e0e013d77ce77c89` |
| 黑帧 | 无 |
| 冻结检测（n=0.002, d=1.5） | 0 段 |
| 状态核对 | 起始帧 237 S / 3 I / 0 R；末段约 164 / 20 / 56，计数与画面一致（抽帧核对） |

## 语法检查
- 单镜头 12 s ∈ [6, 30]。
- 首动作在 0%，动作间隔 ≤ 10 s。
- 长寿命对象：agents / curve / counters 全程存活（虽非 `long_take` 不强制要求）。
- 数据与画面同源：计数、曲线、个体颜色均来自同一 `frames[]`。

## 已知不足
- 模拟规模 240 个体，视觉上仍偏稀疏；更大规模需空间网格加速。
- 曲线区域偏窄，作为样片够用，正式片应提高信息层级。
