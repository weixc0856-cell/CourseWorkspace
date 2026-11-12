# 样片记录 · 06-attention-sample（真实中文课程样片）

日期：2026-11-10
性质：真实内容生产验证，不是架构扩展。成片与报告在 `build/06-attention-sample/`（不入库）。
上位设计：[多视觉语法生产系统-设计](多视觉语法生产系统-设计.md)；实施记录：归档 `docs/archive/records-2026-11/architecture/实施记录-P1-P4.md`。

---

## 1. 成片

- 文件：`build/06-attention-sample/final/course-video.mp4`
- 时长：62.187 s（旁白 62.16 s）
- 规格：1920×1080 / 30 fps / H.264 + AAC
- 中文旁白：VoxCPM2，零样本克隆（本机中文参考音）
- 逐词字幕：Remotion `WordCaptions`，底部字幕带
- 镜头：7 个；语法：`kinetic_type` / `long_take` / `data_viz` / `simulation` / `kinetic_edit`；渲染器：Manim + CodeVideo

## 2. Shot Manifest

| # | 镜头 | 语法 | 渲染器 | 起 | 时长 |
| --- | --- | --- | --- | --- | --- |
| 1 | attn-hook | kinetic_type | code_video | 0.00 | 6.16 |
| 2 | attn-geometry | long_take | manim | 6.16 | 14.32 |
| 3 | attn-matrix | data_viz | code_video | 20.48 | 10.64 |
| 4 | attn-flow | simulation | code_video | 31.12 | 14.48 |
| 5 | attn-mask | data_viz | code_video | 45.60 | 7.28 |
| 6 | attn-summary | kinetic_edit | code_video | 52.88 | 4.24 |
| 7 | attn-recap | kinetic_type | code_video | 57.12 | 5.04 |

完整清单：`build/06-attention-sample/reports/shot-manifest.md` / `.json`。

## 3. 中文旁白与 ASR

| 项 | 结果 |
| --- | --- |
| TTS | VoxCPM2，62.16 s，首轮 6 段 593 s；第 7 段 107 s；s005 异常重合成一次 |
| ASR | faster-whisper `small`，`language=zh`，CPU int8 |
| 词数 / 覆盖率 | 225 词 / **0.935**，状态 **PASS** |
| 段边界误差 | 起点 −40…+660 ms，终点 +20…+440 ms |
| 逐词字幕 | ASR 词时间 + 已批准简体脚本，按字符映射，257 字 |

已知：`small` 模型输出繁体且有少量错字；字幕文字以脚本为准，时间以 ASR 为准；未做人工逐字听校。

## 4. 参考逐镜头对照

参考：3B1B《Attention in transformers》（`eMlx5fFNoYc`，26:09），章节时间戳来自视频简介，画面用故事板 L2 抽样。

| 我们的镜头 | 参考 | 结论 |
| --- | --- | --- |
| attn-hook | 0:00–1:39 | 参考从嵌入表进入；我们用大字提问，主动裁掉嵌入表 |
| attn-geometry | 1:39–4:29 | 点积/角度/投影对齐；参考是真实词向量，我们是二维示意（已标注） |
| attn-matrix | 4:29–8:20 | 行/列语义对齐；未讲 softmax |
| attn-flow | 13:10–15:44 | 加权流动对齐；边是权重示意，不是 value 向量本体（已标注） |
| attn-mask | 11:08–12:42 | 因果遮罩形状对齐；未讲上下文长度 |
| attn-summary | 无直接对应 | 课程化三步总结 |
| attn-recap | 24:54–26:09 | 以问题收尾；无下一集预告 |

`reference-compare`：timing pass / motion pass / **camera pass**（修正了此前 camera_movement fail）；composition / visual_hierarchy / typography = human_review。

## 5. 质量门禁

- `quality-gate`：hard pass / grammar pass / metrics 99.0（metric_only）/ human review required。
- `media-qc`：WARN；loudness/level policy WARN，8 段 freeze WARN，字幕 PASS，speech_match PASS。
- `quality-report`：BUILD_PASS=True；Q1/Q2 INCOMPLETE（未跑 ContentQA / Teaching QA）；Q3 WARN；Q4 PASS；Q5 WARN（等待人工发布批准）；**QUALITY_PASS=False**，未冒充通过。
- 人工验收：`build/06-attention-sample/reports/human-review.md`，结论待签。

## 6. 180 秒分块捕获

- 命令：`capture.mjs build/long-capture-180 --dur 180 --chunk-seconds 60`
- 结果：exit 0；3 段；5400 帧 / 180.000 s；1920×1080 / 30 fps；完整解码无错误；281.9 s。
- 结论：差距清单 #20 在本测试中关闭；但样片是测试图，不是真实课程镜头。

## 7. 仍未达到目标

1. 逐词字幕是字符级，常从词中间开始；未做中文分词/词组。
2. `small` ASR 的中文准确率未与人工转写对照。
3. attn-flow 边偏淡；attn-summary 第二张卡片 0.38 s。
4. 未讲 softmax、value 向量本体、上下文长度、多头。
5. 无 BGM、音效、片头片尾。
6. ContentQA / Teaching QA 未跑，发布批准未签。
7. 180 s 捕获未在真实课程镜头上复测。

## 8. 交付路径

- 成片：`build/06-attention-sample/final/course-video.mp4`
- 镜头清单：`build/06-attention-sample/reports/shot-manifest.md`
- 生产记录：`build/06-attention-sample/reports/production-log.md`
- 参考对照：`build/06-attention-sample/reports/reference-shots.md`
- 人工验收：`build/06-attention-sample/reports/human-review.md`
- ASR：`build/06-attention-sample/quality/asr-alignment.json`、`asr-words.zh.json`
- 质量：`build/06-attention-sample/quality/media-qc.json`、`quality-report.json`、`gate.json`
- 180 s：`build/architecture-samples/long-180.mp4`
