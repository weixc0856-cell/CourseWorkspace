# Sample 2 · 验证结果

## 渲染命令
```powershell
$env:NODE_PATH="$PWD/CodeVideoStudio/shots/compute-topology/node_modules"
node CodeVideoStudio/skills/code-video/scripts/capture.mjs `
  docs/architecture/samples/kinetic-cuts --fps 30 --dur 12 --size 1920x1080 `
  --out $PWD/build/architecture-samples/kinetic-cuts.mp4
```

## 机器结果（2026-11-10 实跑）
| 项 | 结果 |
|---|---|
| 文件 | `build/architecture-samples/kinetic-cuts.mp4` |
| 时长 | 12.000 s |
| 分辨率 / 帧率 | 1920×1080 / 30 fps |
| 编码 / 像素格式 | H.264 / yuv420p |
| 确定性 | 两次捕获 SHA-256 完全一致：`48319f0131cefde3…` |
| 黑帧 | 无 |
| 冻结检测（n=0.002, d=1.5） | **4 段**：1.03、4.43、7.27、9.67 s |

## 语法检查
- 镜头 4 个，每个 3.0 s ∈ [1.5, 8]。
- 切点 3.0 / 6.0 / 9.0，硬切。
- 每镜首动作 ≤ 0.33 s。
- 长寿命对象：无（`kinetic_edit` 不要求）。
- 动作/10 秒：约 6.7，达到 profile 目标 6.0。

## 关键发现（写进架构审计）
冻结检测在**明显有运动**的短切文字片上仍报 4 段：3 秒内文字只占画面不足 0.2% 的像素，`freezedetect=n=0.002` 判定为“冻结”。这说明该检测器不能作为矢量图形/文字片的通用质量门禁，只能作为 metric 或按视觉类型关闭。
