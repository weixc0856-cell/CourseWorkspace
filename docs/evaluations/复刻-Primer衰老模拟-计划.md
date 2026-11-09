# 复刻计划：Primer《Simulating the Evolution of Aging》

日期：2026-11-09
参考：Primer, *Simulating the Evolution of Aging* — <https://www.youtube.com/watch?v=1_JbJTeLZJs>
产物：`build/aging-evolution/final/course-video-mixed.mp4`（2.5 分钟，目标）
源码：`CodeVideoStudio/shots/primer-aging/`、`lessons/aging-evolution/`

## 1. 目标与边界

复刻的是**内容逻辑与视觉效果**，不是逐字脚本或原片素材：

- 内容：为什么选择没有造出永生的身体；年龄越大选择越弱；突变累积（Medawar）；拮抗性多效（Williams）；外在死亡率如何改变寿命与死亡曲线。
- 视觉：Primer 式的低多边形模拟世界 + 实时 HUD（种群、死亡年龄、突变负荷、死亡风险曲线）+ 缓慢有动机的相机。
- 边界：模型是玩具模型，不拟合真实物种；旁白为候选脚本，需人工审校后才可作为对外课程。

## 2. 架构

```text
simulate.py  ──► aging.json（两套环境：危险 / 安全）
gen_narration.py ──► audio/*.wav + timing.json（VoxCPM2）
assemble.py  ──► narration.wav + subtitles.srt + bilingual.draft.json + shot timing.json
main.js      ──► 世界 + HUD，window.seek(t) 纯函数
capture.mjs  ──► 1920×1080 / 30 fps 世界片
CourseControl build ──► 合成旁白、烧录字幕、QC、评分
```

- 世界片由 `code_video` 适配器捕获（`ShotSpec.scene` 指向 `SPEC.md`）。
- 课程 `compose.mode: scene`，`scenes/manifest.json` 的 `base_file` 指向世界片。
- 旁白、字幕、音乐由既有流水线负责；三维只提供干净的底。

## 3. 阶段

### P0（本轮）——可看的完整切片

- 12 段英文旁白（约 2.5 分钟），VoxCPM2 本地合成，双语字幕。
- 两套环境的 agent 模拟：基因组、年龄、繁殖、外在死亡率。
- 3D 世界 + HUD：年龄配色、种群、平均死亡年龄、晚期突变数、死亡风险曲线。
- 课程骨架、节拍表、narrative plan、构建、QC、评分。

验收：构建 pass；字幕/音画对齐；媒体 QC 无 FAIL；`animation-score` ≥85；人工完整看一遍。

### P1——质感对齐（进行中）

1. 生物资产：低模身体/肢体、觅食/繁殖动作，替换“球 + 眼睛”。已完成第一版：身体 + 四条腿的行走摆动；仍无觅食/繁殖动作。
2. 地形与生物群系：已完成第一版：浅盆地地形 + 散石；仍缺植被/水面。
3. 后处理：已完成第一版——官方 three.js r160 addons 链（`BokehPass` 景深、`UnrealBloomPass` 泛光、`ColorCorrectionShader` 调色、`FilmPass` 颗粒、`VignetteShader` 暗角、`OutputPass` ACES/sRGB、`FXAAShader`）。捕获改为 `capture.json` 显式开启 GPU + JPEG 中间帧：36 ms/帧（SwiftShader + PNG 777 ms/帧）。详见 D-061。
4. 叠加层：当前 HUD 内嵌在世界片里；统一的 Remotion 图表层未做。
5. 音频：已接入 Schubert D.664（公版）BGM，ducking 由 `audio-mix` 完成；音效与词级对齐未做。

### P2——内容深度

1. 更接近参考片的三段模拟：危险世界 → 安全世界 → 干预（降低外在死亡率/改变繁殖年龄）。
2. 统计面板：寿命分布、基因频率、选择梯度。
3. 真实文献引用与人工审校（Medawar 1952；Williams 1957；Hamilton 1966）。

## 4. 风险与诚实话术

- 模拟参数为清晰性选择，不是拟合值；片中必须说“玩具模型”。
- 旁白由 Claude 起草，未经人类逐字批准；对外发布前需审校。
- 3D 世界仍是程序化低模，不是参考片的完整资产；差距在 P1 收敛。

## 5. 证据

- 模拟数据：`build/aging-evolution/aging.json`（本地；脚本可复现）。
- 旁白：`build/aging-evolution/narration/narration.wav` + `narration.meta.json`。
- 世界片：`build/aging-evolution/animation/primer-aging.mp4`。
- 成片与 QC：`build/aging-evolution/final/`、`quality/media-qc.json`。

## 6. 本轮结果（2026-11-09）

- 成片：`build/aging-evolution/final/course-video-captioned.mp4`（1920×1080 / 30 fps / 145.37 s / 4,361 帧，含旁白与双语字幕）。
- 构建：`verdict=pass`；`QUALITY_PASS=True`（Q1/Q2/Q5 为 WARN，Q3/Q4 PASS）；`RELEASE_APPROVED=False`（人工审校未做）。
- 媒体 QC：全部 PASS；`freeze=0`；静音 0（BGM 填充片尾）；BGM 混音 `status=pass`；字幕 32 cue；ASR 覆盖 0.935。
- 字幕：32 cue，按策略拆分（≤6 s、英文 ≤2 行 42 字符、中文 ≤2 行 15 字符、CPS ≤9）；ASR `small.en` 覆盖 0.935，0 条 cue 不一致。
- 对齐评分：100/100（运动 25、连续性 20、节奏 15、相机 10、门禁 15、冻结 15）。
- 旁白：12 段，VoxCPM2 reference-only 模式；共 285 词；本地合成约 35 分钟。

已知缺口：生物仍是“球 + 眼睛”；无地形/后处理；BGM 未接；旁白为 Claude 起草，未经人类逐字审校；模型为玩具模型。

## 7. 结论

P0 完成：我们已经有能力用现有流水线端到端复刻该参考片的**机制与视觉语言**（模拟世界 + HUD + 旁白 + 双语字幕 + QC/评分），并且这条链路是可复现、可校验的。下一步按 P1 提升质感，再按 P2 增强内容深度。

## 8. P1 后处理增量结果（2026-11-09）

| 项 | 结果 |
| --- | --- |
| 成片 | `build/aging-evolution/final/course-video-mixed.mp4`：1920×1080 / 30 fps / 145.4 s / 4,361 帧 |
| 构建 | `verdict=pass`；`render:code_video` 152 s（此前为 12 分钟级）；`compose` / `burn_subtitles` / `verify` 全部 pass |
| 后处理 | 官方 r160 addons：`BokehPass` 景深（焦点跟随世界中心）、`UnrealBloomPass`（阈值 1.8，线性 HDR）、`ColorCorrectionShader`、`FilmPass` 颗粒（时钟绑定 `t`）、`VignetteShader`、`OutputPass`（ACES + sRGB）、`FXAAShader` |
| 捕获 | `capture.json` 开启 `--gpu --jpeg`：36 ms/帧；SwiftShader + PNG 为 777 ms/帧。JPEG 中间帧与 PNG 同一帧对比 40.34 dB vs 40.56 dB |
| 确定性 | GPU 路径两次 30 帧捕获 sha256 一致 |
| 媒体 QC | 十项全 PASS：解码、格式、帧数、响度 −16.2 LUFS / −3.2 dBTP、电平策略、静音 0、黑帧 0、冻结 0、字幕 32 cue、ASR 覆盖 0.935 |
| 质量报告 | `BUILD_PASS=True`、`QUALITY_PASS=True`（Q3/Q4 PASS，Q1/Q2/Q5 WARN）、`RELEASE_APPROVED=False`（人工审校未做） |
| 对齐评分 | `animation-score = 100/100` |

已知缺口：生物仍是程序化低模（无觅食/繁殖动作）；地形已有但缺植被与水面；HUD 仍内嵌在世界片里，Remotion 叠加层未做；旁白为候选稿，未经人工逐字审校。
