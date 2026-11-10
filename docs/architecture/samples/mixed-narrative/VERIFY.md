# Sample 4 · 验证结果

## 组装命令
```powershell
# 1) 标题卡（CodeVideo）
$env:NODE_PATH="$PWD/CodeVideoStudio/shots/compute-topology/node_modules"
node CodeVideoStudio/skills/code-video/scripts/capture.mjs `
  docs/architecture/samples/mixed-narrative/title-card --fps 30 --dur 3 --size 1920x1080 `
  --out $PWD/build/architecture-samples/mixed-title-card.mp4

# 2) 四段统一到 1920×1080/30，再无损拼成一条时间线
ffmpeg -ss 0   -t 3 -i LongTakeGeometry.mp4 -vf "fps=30,scale=1920:1080,format=yuv420p" ...
ffmpeg -ss 3.2 -t 3 -i kinetic-cuts.mp4 ...
ffmpeg -ss 7   -t 3 -i population-sim.mp4 ...
ffmpeg -f concat -safe 0 -i list.txt -c:v libx264 -pix_fmt yuv420p mixed-narrative.mp4
```

## 机器结果（2026-11-10 实跑）
| 项 | 结果 |
|---|---|
| 文件 | `build/architecture-samples/mixed-narrative.mp4` |
| 时长 | 12.000 s |
| 分辨率 / 帧率 | 1920×1080 / 30 fps |
| 编码 / 像素格式 | H.264 / yuv420p |
| SHA-256 前 16 位 | `8aee7a95658d85e3` |
| 黑帧 | 无 |
| 冻结检测（n=0.002, d=1.5） | 2 段：0.5 s、3.0 s（标题卡停留与拼接边界，误报） |

## 语法检查
- 四个镜头分别按 `kinetic_type` / `long_take` / `kinetic_edit` / `simulation` 检查。
- 不存在全片统一的镜头长度或长寿命对象要求。
- 每段都可由自己的渲染器独立重渲，再拼接。

## 结论
混合时间线在现有渲染能力内可直接完成：缺的不是渲染器，而是**镜头级契约与按语法分档的验收**。这正是本轮设计的 P1/P2。
