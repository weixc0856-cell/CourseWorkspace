# C-26 新闻片密度修订（2026-11-10）

- 对象：`lessons/nvda-gpu-control`（354.3 s，8 页）
- 问题：每页底部 80–120 字中文段落与口播/字幕重复，视频尺度下字号过小
- 原则：不改旁白、不改时长、不加速语速；只调整画面信息层次

## 1. 实际修改

- 删除 8 页 `<div class="zh-sub">…</div>` 中文段落；中文继续由字幕承担。
- 保留英文要点、日期、引语、来源与判断标签。
- 未改 `narration.script.json`、`narration.wav`、page 时长预算或镜头顺序。
- 镜头时长未调整：旁白与事实未变，改动时长会破坏音画同步；信息密度通过删重复文字与恢复英文层级解决，不靠加速语速。
- 修复 cue 15：`Megaspeed` → `名为 Megaspeed`，满足双语字幕完整性（不涉及口播）。

## 2. 事实与观点

| 页 | 性质 | 处理 |
| --- | --- | --- |
| 01 | 事实：道歉信、董事会声明 | 保留来源与日期 |
| 02 | 事实 + 报道中的关注点 | 保留“reported concern”措辞 |
| 03–05 | 技术/结构解释 | 保留三层证据与五方结构 |
| 06 | **明确标注 MY JUDGMENT** | 保留三条判断与“What this is not” |
| 07 | 开放问题 | 保留，不加预测 |

没有新增事实、没有把判断写成结论。

## 3. 前后对比

| 帧 | 文件 |
| --- | --- |
| 第 1 页 12 s 前 | `before-slide1.png` |
| 第 1 页 12 s 后 | `after-slide1.png` |
| 第 2 页 30 s 前 | `before-slide2.png` |
| 第 2 页 30 s 后 | `after-slide2.png` |
| 15 秒片段（前） | `sample-before.mp4` |
| 15 秒片段（后） | `sample-after.mp4` |

修订后视频：`build/nvda-gpu-control/final/course-video.mp4`（354.304 s）。修订前备份：`build/nvda-gpu-control/final/course-video-before-c26.mp4`。

## 4. 状态

- 内容密度与可读性：已修订并重建，V-14/V-27/V-28/V-31/V-44 通过。
- 是否达到发布级视觉：需人工看片；本轮只证明中文重复段落已移除、英文层次可读。
- 未通过单纯加快语速解决问题；旁白与时间轴未改。
