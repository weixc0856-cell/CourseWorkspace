# VERIFY — WAYNE desktop opener v2

日期：2026-11-10
成片：`out/wayne-opener.mp4`

## 工程核验

| 项 | 结果 | 证据 |
| --- | --- | --- |
| 格式 | pass | 1920×1080 / 30 fps / 600 帧 / 20.000 s / yuv420p / 无音轨 |
| 每帧是 `t` 的纯函数 | pass | 无 `Math.random`、无 wall-clock；纸纹用固定种子；角色几何来自 `character.json` |
| 两次渲染一致 | 本版未复测 | 上一版（卵形角色）两次 sha256 一致；v3 换角色后未再跑第二次 |
| 事件落点 | pass（±3） | 帧差峰值：入场 f13、点击 f152、展开 f179、回车 f256、曲线完成 f327、开始拖动 f369、W 起笔 f518、W 完成 f544、电流 f586 |
| 角色来自 Blender | pass | `build_character.py` → `character.blend` / `character.json`（75 个部件 / 41,464 三角形；影片中按 0.55 缩放装配）；three.js 只做装配与动画 |
| W 正对镜头 | pass | 收尾时纸板立起，法线朝向镜头；W 以斜接四边形描出，转折无缺口 |
| W 路径 | pass | `W_PATH` / `CURRENT_PATH` 逐字取自 `RemotionStudio/src/brand/BrandMark.tsx` |
| 橙色单一焦点 | 基本通过 | 天线尖 → 涟漪 → 光标 → 曲线末端 → 电流；f255–f270 回车涟漪与末端点同属"结果"焦点 |

## 已知限制

- 角色是 Blender 基础体量组合，造型干净但细节有限；表情只有面罩开合。
- 无音轨；节拍只体现在动作时间轴。
- 材质为程序纸纹 + 单一方向光，阴影偏硬。
- 小屏可读、连续观看 3 次的舒适度、最后 3 秒单独的品牌识别度：**未做人工验收**，需要人看。

## 命令

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup `
  --python build_character.py -- .
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur 20 --size 1920x1080 --out out/wayne-opener.mp4 --gpu
```
