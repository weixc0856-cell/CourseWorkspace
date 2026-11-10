# NVDA 新闻片编辑审阅（2026-11-10）

- 对象：`lessons/nvda-gpu-control`，354.304 s，116 cue
- 依据：`quality/asr-alignment.json`、`slides.md`、`lecture_notes.md`、`authoring/source-digest.md`
- 原则：不为了 ASR 全绿修改正确短句或专有名词；只修真实时间轴问题

## 1. 六条 ASR mismatch 逐条判定

| cue | 字幕 | ASR | 判定 | 处置 |
| ---: | --- | --- | --- | --- |
| 1 | on the eighth of november | on 8 november nvidia | 日期写法差异，ASR 把下一 cue 的 NVIDIA 提前 | 不改文本 |
| 15 | called megaspeed | megaspit which has | 专有名词 ASR 误识别 | 不改文本 |
| 71 | on the thirty first of october | own position on the 31st | 日期写法差异 + 边界 | 不改文本 |
| 81 | the data centre operator | maker the data center | 字幕提前约 0.7 s，跨到上一句 | 已重定时 80–84 |
| 112 | who is using it | compute who is | 字幕提前约 0.8 s | 已重定时 111–116 |
| 113 | who controls it | is using it who | 同上，连续错位 | 已重定时 111–116 |

重定时只改 cue 起止时间与相邻边界，文字未改。重跑后 ASR 只剩 **3 条**（cue 1、15、71），均为日期写法/专名识别问题；80–84、111–116 已对齐。4 条日期/专名差异保留，避免为了分数改正确内容。

## 2. 事实、推断与观点

| 类型 | 内容 | 检查 |
| --- | --- | --- |
| 事实 | 道歉信原文、董事会声明、BIS 2025-05-13 指导、Bloomberg 10-30 引语、新加坡 10-31 声明 | 与 `source-digest.md` 的 S1–S5 对齐 |
| 推断 | “私人事务为何变成国家安全问题” | 以问句提出，未写成结论 |
| 观点 | 第 06 页 `MY JUDGMENT` 三条判断 | 明确标注；同页 `What this is not` 声明不是泄密证据 |

未发现无来源的新事实，也未把观点写成事实。

## 3. 前 30 秒信息密度

- 0–30 s 只有第 1 页静态画面：日期、道歉引语、董事会调查声明。
- 口播/字幕在 30 s 内推进了：道歉 → 独立调查 → 董事会信心 → 众议院闭门简报 → “为何成为国家安全问题”。
- 画面本身在 5 s 后没有新增视觉信息；信息增量由字幕承担。
- 本轮已移除该页底部重复的中文段落，英文主信息可读；未拆分页面或新增图形，因为会改动旁白与 page 时长。
- 后续建议（不阻塞）：把第 1 页拆成“声明”和“问题”两屏，或加一张来源卡；需要单独改版与重跑。

## 4. 本轮实际修改

- 删除 8 页中文 `zh-sub` 段落，中文交给字幕。
- cue 15 补 `名为 Megaspeed`，满足双语完整性；不改口播。
- cue 80–84、111–116 按 ASR 词边界重定时；文字未改。
- 未改旁白、语速、page 时长预算或镜头顺序。

## 5. 状态

- `ENGINEERING_VERIFIED`：重建后 `verdict=pass`，V-44 PASS；ASR 覆盖 0.919，3 条 mismatch。
- 编辑审阅：事实/观点分层成立；前 30 秒画面增量偏低，记录为后续版式改进。
- `CONTENT_VERIFIED` 仍由所有者最终签核。
