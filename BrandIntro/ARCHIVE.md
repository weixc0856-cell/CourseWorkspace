# 归档记录 — 2026-11-10

状态：**暂停。** 用户决定先不做，保留现有成果与判断，便于以后续上。
没有未完成的后台任务；没有提交到仓库（工作区改动未 commit）。

## 1. 做出过什么

### 成片与片段（本地，`CodeVideoStudio/shots/brand-intro/out/`）

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `wayne-atelier.mp4` | 20 s / 600 帧 / 1080p30 / 无音轨；工作室场景 + 角色 + 曲线 + 纸板收尾 | 当前最新整片 |
| `wayne-opener.mp4` | 20 s；旧场景（空白纸面）+ 创作者机器人 | 上一版，保留对照 |
| `brand-rise.mp4` | 3 s / 72 帧；纸板从台阶翻起、角色让位 | 收尾动作验证 |
| `env-wide/medium/close.png` | 工作室全景/中景/近景（Blender，1600×900） | 场景 Gate 帧 |
| `env-light-key-only/key-fill/key-fill-rim.png` | 三组灯光对比 | 场景 Gate 帧 |
| `env-brand-front/wide.png` | 品牌纸板正面与全景 | 收尾概念帧 |
| `concept-{atelier,studio,bench}-{wide,medium,close}.png` | 三套场景方向概念帧 | 方向比较 |

### 工程文件

| 文件 | 作用 |
| --- | --- |
| `build_character.py` | Blender 建角色（创作者机器人，75 部件 / 41k 三角形），导出 `character.json` + 四视图 |
| `build_scene.py` | Blender 建工作室场景；`--brand` 出品牌纸板；`--brand --anim` 出立起动画 |
| `character.blend` / `scene.blend` | 可编辑源文件 |
| `film.html` / `film.js` | 20 秒整片的 three.js 场景与时间线 |
| `scene.html` / `scene.js` | 三套场景概念帧的探针页 |
| `main.js` | 旧版（空白纸面）整片 |
| `SPEC.md` / `VERIFY.md` / `GATE1.md` | 规格、核验、旧 Gate 1 记录 |
| `BrandIntro/gates/GATE_ENV.md` | 场景 Gate 与结果 |
| `BrandIntro/art_direction/*` | 参考板、角色概念、场景概念、材质灯光、镜头语言 |

## 2. 走过的判断（按时间）

1. 参考片方向成立：吉祥物当光标，在桌面上点击/打字/拖拽，收尾成品牌。
2. 第一版纸片角色 → **否决**（"纸片人"在中文语境有贬义）。
3. 第二版卵形陶瓷角色 → **否决**（没有身份、结构逻辑、品牌专属感）。
4. 按用户给的参考图重建：大头、深色面罩、橙色眼、铜描边、分节手臂、夹爪 → 采用。
5. 场景从无限灰地重建为微缩建筑工作室（墙、窗洞、三级台阶、道具）→ 采用。
6. 收尾从"贴一块牌子"改为"纸板从台阶翻起、立到窗洞前"→ 采用，动作已渲染。
7. 角色缩小到 0.55 倍，与纸面比例协调。

## 3. 验收状态

| Gate | 状态 | 缺口 |
| --- | --- | --- |
| 参考板 | 文档在，未逐帧核对 | 20 条参考未截图 |
| 角色 | 实体建模完成，未过 Gate | 表情只有面罩/眼，缺雕刻级细节 |
| 场景 | 空间/材质/灯光方向通过；品牌收尾动作通过 | 材质仍是程序纹理；道具偏少 |
| 融合 | 部分通过 | 角色与道具尚无真实互动 |
| 表演 | 未单独验证 | 跑跳是位移 + 起落，无完整步态 |
| 成片 | 有一条 20 秒原型 | 无音轨；未做 8 秒版；未接生产链 |

## 4. 已知差距（若续做）

按优先级：

1. **音频**：120 BPM 的动作时间轴已经在，缺的是一条踩拍的音轨（三层：低频脉冲 / 动作音效 / Audio Signature）。
2. **纸张形变**：纸板现在是刚体翻转；需要弯曲、厚度、边缘受光的变化。
3. **角色雕刻**：头盔磕碰、面板接缝、磨损；或导入刻好的模型替换 `character.json`。
4. **材质**：墙面矿物涂层、木材、纸纤维的扫描/手绘贴图，替代程序噪声。
5. **融合**：角色拿起直尺、推动纸张、把结果递出去——目前只是站在旁边。
6. **工程**：两次渲染一致性复测；8 秒课程版；与 `course-control brand-*` 的接入方式。

## 5. 续上时怎么开始

```powershell
# 角色
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup `
  --python CodeVideoStudio/shots/brand-intro/build_character.py -- CodeVideoStudio/shots/brand-intro

# 场景 / 收尾动作
& "...\blender.exe" --background --factory-startup `
  --python CodeVideoStudio/shots/brand-intro/build_scene.py -- CodeVideoStudio/shots/brand-intro --brand --anim

# 整片
cd CodeVideoStudio/shots/brand-intro
node ../../skills/code-video/scripts/capture.mjs . --page film.html --fps 30 --dur 20 --size 1920x1080 --out out/wayne-atelier.mp4 --gpu
```

先读 `BrandIntro/README.md` 与 `gates/GATE_ENV.md`，再决定从上面六个缺口里的哪一个开始。

## 6. 一句总结

方向是对的：一个干净的工作室、一个小创作者、一次计算、一张纸变成品牌。技术链路已经跑通，剩下的都是美术深度与声音，不是可行性问题。
