# SPEC — WAYNE desktop opener (v3, creator robot)

- **Project**: `CodeVideoStudio/shots/brand-intro`
- **Purpose**: a 20 s opener in the reference's animation language (a character acting as the cursor on a desk: click, type, drag, beat-timed camera and result), with a character modelled in Blender and the brand mark standing upright at the end.
- **Character**: small creator robot designed from the user's reference — large helmet head, dark glossy visor with two warm eyes, copper trim, ear discs, antenna, chest panel with badge and rivets, segmented arms with joint rings, pistons and gripper hands, short legs with big feet. Built by `build_character.py` (75 parts, 41,464 triangles); the `.blend` is kept for edits. In the film the rig is assembled at 0.55 scale so the robot reads as a small creator against the paper props; the helmet and torso get a light displacement pass (0.0012–0.0018 m) to avoid perfect primitives.
- **Stack**: Blender 5.2 (modelling + preview) → `character.json` (per-part geometry, Y-up) → three.js r160 + vendored r160 addons (Bokeh / Bloom / Vignette / Output / FXAA).

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Frames | 600 (0–599) |
| Duration | 20.0 s |
| Audio | none (music is a later stage) |
| Tempo grid | 120 BPM, 0.5 s per beat |

## Narrative

| 时间 | 事件 |
| --- | --- |
| 0.5–1.05 | 角色跳入，落在纸面上 |
| 1.05–3.5 | 站定、环顾、发现桌上的卡片 |
| 3.5–5.0 | 跳到卡片左侧，伸手点击（涟漪） |
| 5.0–5.6 | 卡片展开成工作纸面 |
| 6.0–8.0 | 打字 `$ render lesson`，8.5 回车 |
| 9.0–11.0 | 阶跃响应曲线生长，末端点出现 |
| 12.3–14.1 | 抓住纸面，把结果拖到左侧 |
| 15.0–16.5 | 退到画面外，把纸面留给品牌 |
| 16.4–17.6 | 纸面离开桌面、立起，正对镜头 |
| 17.2–18.2 | W 四笔以斜接（miter）方式描出，无接缝 |
| 18.4 | WAYNE 与副标落在纸面上 |
| 19.5–19.7 | 橙色电流亮起，定格 |

## Must-haves

1. 每帧是 `t` 的纯函数；无 `Math.random`、无 wall-clock；纸纹用固定种子生成。
2. 角色来自 Blender 几何（`character.json`），不是程序化平面拼接。
3. 一条连续长镜头，无切点、无淡入淡出。
4. 橙色任一时刻只有一个焦点（天线尖、涟漪、光标、末端点、电流）。
5. 文字全英文，终端行在 96 px 安全边距内。
6. W 的路径逐字复用 `BrandMark.tsx` 的 `W_PATH` / `CURRENT_PATH`；正对镜头，不平躺、不倾斜。
7. 后处理只用已 vendored 的 r160 addons。

## Commands

```powershell
# 1. build the character (writes character.blend / character.json / character-preview.png)
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup `
  --python build_character.py -- .

# 2. render
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur 20 --size 1920x1080 --out out/wayne-opener.mp4 --gpu
```

## 已知问题（v2）

- 角色是 Blender 基础体量（球体 + 圆角盒）组合，造型干净但细节有限；表情只有面罩开合。
- 没有音轨；踩拍只能从动作时间轴看出来。
- 材质是程序纸纹 + 单一方向光；阴影偏硬。
- 桌面留白很大，节奏主要靠相机和动作。
- 两次渲染一致性已复测并记录在 `VERIFY.md`。


## Atelier cut (2026-11-10)

`film.html` / `film.js`：把场景、角色、纸上的曲线和纸板收尾接成一条 20 秒长镜头。

- 场景：微缩建筑工作室（墙、窗洞、三级台阶、图纸卷、纸模型、铅笔筒、纸叠、铜镇纸）。
- 角色：Blender 建模的创作者机器人，站在纸面左侧工作，收尾时向右跳三步让位。
- 结果：阶跃响应画在台阶上的纸面里（10–12 s）。
- 收尾：纸板从台阶后方翻起、退到窗洞前立住（13.4–15.4 s），W 以斜接方式描出（15.5–16.6 s），字标 17.6 s 落位。
- 成片：`out/wayne-atelier.mp4`（20 s / 600 帧 / 1080p30 / 无音轨）。

已知差距：角色仍是基础体量；板子是整体翻转，没有纸的形变；材质为程序纹理；没有音轨；没有做两次渲染一致性复测。
