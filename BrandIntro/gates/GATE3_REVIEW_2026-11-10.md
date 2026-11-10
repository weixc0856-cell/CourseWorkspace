# Gate 3 复核（2026-11-10）

- 对象：`CodeVideoStudio/shots/brand-intro/` 的 20 秒工作室原型
- 正确渲染入口：`film.html` → `film.js`（不是 `index.html` / `main.js`）
- 结论：**Gate 3 未通过；已修复可证明的视觉缺陷，最终美术签核仍由人决定**

## 1. 修复前后

| 项 | 修复前 | 修复后 |
| --- | --- | --- |
| 文件 | `out/wayne-atelier.mp4` | `out/wayne-atelier-v2.mp4` |
| sha256 | `d1007e76…f9483` | `195d5f24…a6e83` |
| 时长 | 20.0 s | 20.0 s |
| 5 s 帧 | `evidence-2026-11-10/before-05s.png` | `evidence-2026-11-10/after-05s.png` |
| 19.6 s 帧 | `evidence-2026-11-10/before-19.6s.png` | `evidence-2026-11-10/after-19.6s.png` |

## 2. Gate 3 失败项与实际原因

| 失败项 | 实际画面 | 原因 | 本轮处置 |
| --- | --- | --- | --- |
| 背景不是品牌纸面 | 5 s / 19.6 s 的背景偏暖灰，背板是深卡其色 | 场景 `wall` 与背板材质使用 `#F3F0E8` / `#B9B0A0`；与 2D `paper #FBFAF7` 不一致 | `wall` 与背板改为 `#FBFAF7`；曝光 0.94 → 1.02 |
| 空间边界丢失（第一次尝试） | 墙、地、台面同时变白，桌面边缘消失 | 地面/台面也接近纸白 | 恢复地面 `#D8D1C5` 与台面 `#EFEAE0` 的层次 |
| 角色偏小 | 5 s 时角色只占画面约 1/8 高 | 16:9 全景 + 0.55 缩放 | 保留原构图（收紧镜头会裁掉桌面）；作为未解决项记录 |
| 品牌符号出现方式 | W 从立起的纸板生长，橙色电流在最后 1.6 s 才出现 | 叙事把品牌放在收尾，而非角色动作 | 未改 W 路径与电流；Gate 3 第 1 条仍为部分满足 |

橙色电流**存在**，审计中"3D W 没有橙色电流"只对更早的 `wayne-opener.mp4` 成立；当前 `wayne-atelier` 与 v2 的末帧都有 `CURRENT_PATH`。

## 3. Gate 3 三项标准复核

| 标准 | 判定 | 依据 |
| --- | --- | --- |
| 品牌符号自然出现 | **部分** | W 由纸板升起后逐段生长，不是最后叠加；但它不来自角色动作 |
| 一个叙事 | **部分** | 角色工作 → 曲线 → 纸板；四段能连起来，但曲线与品牌之间的关系仍弱 |
| 最后 3 秒单独成立 | **通过** | 末帧是完整 WAYNE lockup + tagline |
| 无声音也能看懂 | **通过（人工初看）** | 动作顺序可读；未做正式无音轨测试 |
| 连看 3 次不烦 | **未执行** | 需要人工重复观看 |

## 4. 复现

```powershell
cd CodeVideoStudio/shots/brand-intro
node ../../skills/code-video/scripts/capture.mjs . --page film.html \
  --fps 30 --dur 20 --size 1920x1080 --out out/wayne-atelier-v2.mp4 --gpu
```

## 5. 状态

- `ENGINEERING_VERIFIED`：渲染成功、20 s / 1080p30、可复现入口已注明。
- `VISUAL_VERIFIED`：**未通过**。背景与层次已修正，角色比例与品牌叙事仍需人工判断。
- 不接入 `course-control brand-*`，不改 `lesson.yaml.branding`。
