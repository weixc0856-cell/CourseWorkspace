# 任务书：风水第一期 A/B/C 视觉压力测试

- **日期**：2026-11-14
- **对象**：`fengshui-wind-water` 的“山谷推进 → 风场解释”段落
- **目的**：用同一段脚本、同一段音乐、同一组字幕，比较三种视觉语言；决定主视觉、过渡/氛围、知识解释的分工，不做单一审美排名。
- **状态**：待执行。本文是任务书，不是门禁；不改变风水频道“无旁白”的现行规则。

---

## 1. 测试段落

从现有 152 s 成片取 **19.05–57.14 s**，共 38.09 s。选这一段的原因：它同时需要空间（山谷）、文化（原文/山水）、机制（风场/图表）和水的作用，三种视觉语言都必须回答同一组问题。

抽取：

```powershell
ffmpeg -ss 19.05 -t 38.09 -i <内容根>/build/fengshui-wind-water/audio/wind-water-126.m4a `
  -c copy <内容根>/projects/fengshui/experiments/ab-2026-11/shared/ab-audio.m4a
```

音频文件以实际为准；先确认源文件名与编码，再抽取。三版必须使用同一个 `ab-audio.m4a`，不重新配乐、不重新节拍。

## 2. 共享脚本与六拍

同一段文字、同一组字幕、同一节拍，三版只换视觉。字幕从 `RemotionStudio/src/fengshui/data.ts` 的 `CAPTIONS` 取 `quote` / `ridge` / `sim` / `chart` / `water`，时间重排到 0–38.09 s。

| beat | 时间 | 英文上屏 | 中文下屏 | 画面任务 |
| --- | --- | --- | --- | --- |
| cold_open | 0.00–6.00 | QI SCATTERS IN WIND. IT STOPS AT WATER. | 气乘风则散，界水则止 | 先给原文与空间 |
| question | 6.00–12.00 | A RIDGE IS A WALL. | 山脊是一堵墙 | 山脊与风向关系 |
| intuition | 12.00–19.00 | BEHIND IT, THE WIND DROPS. | 风在背面慢下来 | 背风侧风速下降 |
| mechanism | 19.00–27.00 | 2× AT THE CREST. 0.4× BEHIND IT. | 山顶是开阔地的两倍，背后只剩四成 | 数据/流场解释 |
| test | 27.00–34.00 | WATER STOPS WHAT WIND SCATTERS. | 风把气吹散，水让它停下 | 水与聚落 |
| connect | 34.00–38.09 | HIDE FROM THE WIND. SIT BY THE WATER. | 挡住风，靠近水 | 回到空间，收束 |

`narrative-plan.json` 用这六拍，`form: long`，`target_seconds: 38.09`。三版共用同一份 plan；如果某一版无法在同一拍内完成，记录原因，不偷偷改拍。

## 3. 三个方案

### A｜3D 视觉纪录片

- **引擎**：Blender 场景 + Remotion 合成字幕/音频。
- **必须体现**：前景（近树/岩石）、中景（村落/河道）、远景（山脊/云）、运动层（风/水/雾）。
- **镜头**：远景建立 → 缓慢推进 → 俯视地形 → 局部特写；摄影机运动有动机，不环绕炫技。
- **光照/材质**：真实感优先；景深服务空间，不在需要看清地形时滥用浅景深。
- **风险**：制作时间最长；低采样预览可能掩盖噪点和材质问题，必须以 1080p 对照。

### B｜东方视觉叙事

- **引擎**：Remotion 2.5D（现有 `fengshui` 组件为基线）。
- **必须体现**：宣纸/墨色/朱砂、留白、层次、笔迹生长、山水到地形的连续过渡。
- **镜头**：推、移、局部显影；不靠转场特效；空间连续。
- **风险**：最容易接近现有成片；必须证明它不只是“现有画面加一点运动”。

### C｜科学可视化

- **引擎**：Manim / SVG / Remotion（三者可组合）。
- **必须体现**：地形高程、山脊剖面、风向/风速、背风侧衰减、水与聚落关系；至少一张真实数据或明确标注的模拟图。
- **镜头**：以信息变化为切点；图表、剖面、流场、关系图为主。
- **风险**：容易变干；需要有视觉重心和节奏，不是四张图表轮播。

## 4. 每版交付物

目录：`<内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/`

| 文件 | 内容 |
| --- | --- |
| `project.yaml` | `mode: topic_video`；`entry` / `composition`；`target_seconds: 38.09`；`delivery_dir` 指向本实验目录，不写 `deliver/`；`licences` 声明共用音乐（CC BY 3.0 + 署名） |
| `1080p.mp4` | 正式分辨率；H.264/AAC；30 fps；1080×1920 |
| `480p.mp4` | P1 预览；短边 480（480×854） |
| `contact-sheet.jpg` | 至少 12 帧；覆盖六拍 |
| `render.json` | 引擎版本、渲染参数、耗时、缓存命中 |
| `assets.md` | 使用到的模型/纹理/字体/音乐/数据来源与许可 |
| `notes.md` | 已知限制、预览与 1080p 的差异、失败尝试 |
| `src/` | 场景/合成源码；可重建 |

共享目录：`shared/ab-audio.m4a`、`shared/captions.srt`、`shared/narrative-plan.json`、`shared/beats.md`。

每版有自己的 `index.ts` 与 `registerRoot`，不修改 `RemotionStudio/src/index.ts`，避免实验污染正式合成。

**源码位置**：实验源码、Blender 任务、音频、字幕、成片都在 `<内容根>/projects/fengshui/experiments/ab-2026-11/`，仓库只保留程序。Remotion 通过本地 junction `RemotionStudio/src/fengshui-ab` 指向本目录；Blender 任务用绝对路径 `-Task` 运行。不要把这些实验文件提交进仓库。

`project.yaml` 的 `public_assets` 指向内容根里的静态资源目录；渲染前 `course-control` 会把它复制到 `RemotionStudio/public/<name>/`。那是生成副本，已 gitignore，源仍在内容根。Remotion 的 bundler 在 Windows 上不能跟随 `public/` 里的 junction，所以这里用复制而不是链接。

构建目录由 `course-control` 按项目 id 自动创建，位置在内容根的 build 下；不写 `deliver/`。

## 5. 执行步骤

每版相同：

```powershell
# 1. 项目契约
course-control project-validate --project <内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/project.yaml

# 2. 叙事契约（三版共用 shared/narrative-plan.json 的副本）
course-control narrative-validate --project <内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/project.yaml

# 3. 预览成本记录（P0/P1/P2；38 s 片子的 P2 可能等于 P1，照跑）
course-control preview-pilot --project <内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/project.yaml

# 4. 1080p 对照
course-control render project --project <内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/project.yaml --mode release

# 5. 发布前只查交付质量，不查风格
course-control release-check --project <内容根>/projects/fengshui/experiments/ab-2026-11/<a|b|c>/project.yaml
```

如果某版由 Blender/Manim 单独渲染，再用 Remotion 合成字幕/音频：

```powershell
# 已有 lesson/storyboard 夹具时
course-control render shot --lesson <slug> --shot <id> --mode preview
course-control render shot --lesson <slug> --shot <id> --mode release
```

没有 lesson 夹具时，把引擎输出当作 composition 的资产，仍用 `render project --project ...` 出预览与正式片；不要让实验变成第二套构建系统。Blender/Manim 的 480p 预览也要保留，不能只留 1080p。

## 6. 评价

### 6.1 共同评价（三版都问）

每条写“成立 / 部分成立 / 不成立 + 证据（时间点、帧、文件）”，不用一个总分排名。

| 维度 | 问题 |
| --- | --- |
| 空间 | 前景/中景/远景/运动层是否成立？空间关系是否看得懂？ |
| 镜头 | 运动是否有目的？是否服务解释，而不是装饰？ |
| 重心 | 每一拍是否有明确视觉主体？观众知道先看哪里？ |
| 声音 | 音乐、环境声、字幕是否与画面形成整体？ |
| 知识 | 是否准确表达脚本中的机制？有没有把示意当成真实计算？ |

### 6.2 方向性评价

| 版本 | 只看这件事 |
| --- | --- |
| A | 空间真实感、摄影机调度、光照与材质是否支撑“纪录片” |
| B | 文化视觉语言是否成立、是否有辨识度、山水到地形的过渡是否连续 |
| C | 机制解释是否更清楚、数据/剖面/流场是否准确、是否仍然好看 |

### 6.3 最终决策

不选“唯一赢家”，回答三个问题：

1. **主视觉**：哪一版承担大部分镜头？
2. **过渡/氛围**：哪一版适合建立空间、转场、留白？
3. **知识解释**：哪一版适合机制、数据、关系图？

写入 `decision.md`，每条给证据。可以组合，例如 B 为主视觉、A 做空间建立、C 做机制解释。

## 7. 验收

- 三版都有 1080p + 480p，时长 38.09 s ±0.1 s；
- 三版使用同一音频、同一字幕、同一六拍；
- 三版都有 `render.json`、`assets.md`、`notes.md`；
- 三版都通过 `release-check` 的交付检查（或明确记录 `INCOMPLETE` 的原因）；`release-check` 只证明交付项满足，不证明视觉/叙事成立；
- 人工看完三版，完成 6.1/6.2/6.3；
- 不把预览产物写进 `deliver/`。

## 8. 角色与边界

- **AI**：辅助场景/合成代码、生成初稿、提出修改建议、跑预览与检查。
- **人**：事实判断、叙事选择、审美判断、最终验收。
- **不做**：不为测试改风水“无旁白”规则；不把 480p 当最终质量；不看代码/脚本判断成片；不因为某一版“更省时间”就直接定为主视觉。

## 9. 风险

| 风险 | 处理 |
| --- | --- |
| A 制作时间过长 | 先做 12 s 单镜头 P0，确认空间和摄影机，再扩到 38 s |
| B 与现有成片太像 | 强制加入一个现有版本没有的空间层或过渡，证明差异 |
| C 太干 | 每张图表必须有一个视觉动作（生长、流动、对照），不做轮播 |
| 480p 掩盖问题 | 每版必须对照 1080p 关键帧；记录预览与成片的差异 |
| 评价变成审美投票 | 用 6.1/6.2 的问题与证据，不用单一分数 |

## 10. 完成后

当前进度：B/C 已有 38.09 s 基线，A 只有 12 s 技术 P0；初步评审见 `<内容根>/projects/fengshui/experiments/ab-2026-11/decision.md`。A 重做并扩到 38 s 后再做最终决定。

把 `decision.md` 与三版 `notes.md` 汇总成一页结论，决定：

- 风水后续集数的主视觉；
- 是否把 Blender 变成这条线的默认引擎；
- 是否把项目级 `visual-design` / `sound-design` 接口排进下一阶段。

在结论出来前，不扩 90 集，不新增视觉模板，不把任何一版写进 `deliver/`。
EOF

---

## 附录 A：单版 `project.yaml` 模板

时间按第 2 节的六拍；`id`、`entry`、`composition`、`output` 按实际版本替换。

```yaml
schema_version: 1
project:
  id: fengshui-ab-a
  mode: topic_video
  title: "FENG SHUI AB — A / 3D documentary"
  language: en
input:
  topic: "风水为什么叫风水 — 山谷与风场"
production:
  quality_profile: premium
  topic_video:
    target_seconds: 38.09
    entry: src/fengshui-ab/a/index.ts
    composition: FengShuiABA
    output: ab-a.mp4
    delivery_dir: projects/fengshui/experiments/ab-2026-11/a
    shots:
      - {id: cold_open, start_s: 0.0,  end_s: 6.0,  label: "quote", segment: ab}
      - {id: question,  start_s: 6.0,  end_s: 12.0, label: "ridge", segment: ab}
      - {id: intuition, start_s: 12.0, end_s: 19.0, label: "wind drops", segment: ab}
      - {id: mechanism, start_s: 19.0, end_s: 27.0, label: "chart", segment: ab}
      - {id: test,      start_s: 27.0, end_s: 34.0, label: "water", segment: ab}
      - {id: connect,   start_s: 34.0, end_s: 38.09, label: "return", segment: ab}
    segments:
      - {id: ab, start_s: 0.0, end_s: 38.09, label: "shared test segment"}
    licences:
      - asset: "music: Guzheng Morning — Antti Luode"
        status: cc_by
        attribution: "Guzheng Morning — Antti Luode, CC BY 3.0"
        commercial_allowed: true
media:
  resolution: 1080x1920
  frame_rate: 30
  video_format: mp4
  audio_format: aac
  subtitles: [srt]
delivery:
  include: [videos, audio, transcripts, sources, quality_report]
execution:
  autonomy: A2
  retry_policy: adaptive
  delivery_policy: quality_gated
```

B/C 两版复制同一文件，改 `project.id`、`title`、`entry`、`composition`、`output`、`delivery_dir`。`shots` / `segments` / `licences` 保持一致。
