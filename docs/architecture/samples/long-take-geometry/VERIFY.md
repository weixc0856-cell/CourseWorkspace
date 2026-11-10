# Sample 1 · 验证结果

## 渲染命令
```powershell
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/architecture-samples/manim `
  docs/architecture/samples/long-take-geometry/scene.py LongTakeGeometry
```

## 机器结果（2026-11-10 实跑）
| 项 | 结果 |
|---|---|
| 文件 | `build/architecture-samples/manim/videos/scene/1080p30/LongTakeGeometry.mp4` |
| 时长 | 8.800 s |
| 分辨率 / 帧率 | 1920×1080 / 30 fps |
| 编码 / 像素格式 | H.264 / yuv420p |
| SHA-256 前 16 位 | `929bb8fe126abddb` |
| 黑帧 | 无 |
| 冻结检测（n=0.002, d=1.5） | 1 段，起于 0.0 s（首帧建立，判为误报） |

## 语法检查
- 镜头数 1，时长 8.8 s ∈ [5, 16]。
- 动作 4 个，首动作在 10% ≤ 35%。
- 相邻动作间隔 ≤ 4 s（0.10→0.22→0.34→0.62→1.0）。
- 长寿命对象 4 类，跨整个镜头存活。
- 相机 1 次，动机 18 字。

## 已知不足
- 首帧有约 1 秒只有标题与网格，冻结检测会报一次；这是"建立"镜头，不是故障。
- q 标签在相机推近后靠近画面上缘，未越界，但离安全区较近。
