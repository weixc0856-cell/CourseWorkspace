# 最终验收报告（2026-11-10 收尾轮）

- 范围：C-01～C-32 遗留项、06 内容修正、NVDA 密度、品牌 Gate 3、05 字幕复核、品牌资产提交
- 原则：工程通过、内容通过、视觉通过、交付包通过、发布批准是五个独立状态，不互相替代

## 0. 状态总表

| 状态 | 结果 | 依据 |
| --- | --- | --- |
| `ENGINEERING_VERIFIED` | **true** | `check.ps1` exit 0；六套单测；06 / NVDA / 05 真实构建；配置、resume、字幕、资产、vendor 检查 |
| `CONTENT_VERIFIED` | **false（机器一致性通过，编辑签核未完成）** | C-25 旁白/字幕/画面已一致；C-26 事实/判断已分开；但措辞与新闻写作仍由所有者最终确认 |
| `VISUAL_VERIFIED` | **false** | Gate 3 未通过：角色比例偏小、品牌 W 与角色动作未形成同一叙事；见 §4 |
| `PACKAGE_VERIFIED` | **true** | 06 / NVDA / 05 的 `package-verify` 通过；哈希复核 |
| `RELEASE_APPROVED` | **false** | 无 review / release 人工签核 |

## 1. R6 验收结论核实

### 1.1 六个跳过用例

| 套件 | 用例 | 原因 | 是否关键 |
| --- | --- | --- | --- |
| CourseControl | `test_generates_valid_v1_contracts` | E6.5 构建产物不在本机 | 否，历史适配器 |
| CourseControl | `test_missing_voice_reference_fails` | 同上 | 否 |
| CourseControl | `test_adapter_reads_v0_without_modifying_it` | E6 V0 产物不在本机 | 否 |
| CourseControl | `test_headless_session_passes` | 需 `COURSE_SESSION_INTEGRATION=1` + Docker | 否，会话录制不在 06/NVDA 路径 |
| CourseControl | `test_wrong_expected_output_fails` | 同上 | 否 |
| ManimSandbox | `test_final_manifest_passes_checks` | E6.5 final manifest 不在本机 | 否 |

没有 06、NVDA、05 主链路依赖的用例被跳过。

### 1.2 06 故障注入与 Resume

真实序列：

1. 首次构建：`attn-*` 缺 Playwright junction，`render:code_video` 失败；`render:manim` 写入检查点。
2. `--resume`：复用 `render:manim`，重跑 code_video/collect，compose 暴露 `--build-root` 路径缺陷。
3. 修复后 `--resume-from compose`：复用 manim/collect，重跑 code_video（输入清单新增 vendor 哈希）与 compose。
4. `--resume`：复用 manim / code_video / collect / compose，只跑 verify，**pass**。

验证到的内容：

- 输入哈希：真实发生——新增 vendor 文件使 code_video 检查点失效。
- 输出哈希：代码在复用前重算，单测覆盖；真实运行中未主动篡改产物。
- 配置指纹：代码与单测覆盖，未在真实运行中改配置触发失效。
- 字幕变化：NVDA 的 `--resume` 记录显示字幕输入使 capture/compose/burn 失效；本轮已收窄检查点输入范围，字幕只失效 consuming stages。

### 1.3 交付包

- 06：22 个文件；外部声线参考打包到 `assets/external/719ce803-my_voice_clean_v1.wav`，`package-verify` 通过。
- NVDA：26 个文件；`package-verify` 通过。
- 05：55 个文件；`referenced_assets` 记录 BGM 与声线参考的 `asset_id`/SHA-256；BGM 在配置库中，不复制进包，因为成片已经混音。**这是“有依赖声明”，不是“包内自带 BGM 源文件”。**

### 1.4 三个“通过”的含义

| 输出 | 只代表 |
| --- | --- |
| `check.ps1` = check ok | 工程回归、契约、单测、类型检查通过 |
| `build-report.verdict=pass` | 本次构建的阶段与检查没有 fail；不代表作品可发布 |
| `package-verify` = package ok | 包内文件与 manifest 哈希一致；不代表内容或视觉合格 |

### 1.5 本轮端到端范围

06 是**单一 64 秒课程**的完整构建（config → validate → render → collect → compose → verify），不是 20 分钟长课 01 的完整生产，也不是多课程批量生产。NVDA 是 354 秒新闻片的完整构建。两者都不等于“所有课程类型已验收”。

## 2. C-25：06 内容矛盾

| 项 | 修改 |
| --- | --- |
| 标题 | `Attention in Ninety Seconds` → `Attention in a Minute`；中文 `九十秒看懂注意力` → `一分钟看懂注意力`；`slides.md` 同步 |
| 因果遮罩 | 旁白 s005、`lecture_notes.md`、SRT cue 11 改为“在解码器里，注意力只能看它前面” |
| 画面 | `attn-mask` 标题改为“解码器：只能看前面”；SPEC 固定文案同步 |
| 时间轴 | s005 6.88 → 9.12 s；全片 62.16 → 64.405 s；production/beats/SRT 重新定时 |

验证：

- 06 重建 `verdict=pass`，V-14 64.400 s，V-31/V-44 PASS。
- ASR 覆盖 0.935，0 cue mismatch。
- 画面帧确认“解码器：只能看前面”与字幕一致。
- 原始版本保存在 `lessons/06-attention-sample/authoring/original-2026-11-10/`；审批记录通过 `author-accept` 写入，措辞的最终编辑签核仍需所有者确认。

## 3. C-26：NVDA 新闻片密度

修改：

- 删除 8 页 `<div class="zh-sub">` 中文段落；中文由字幕承担。
- 未改旁白、page 时长、镜头顺序或语速。
- 修复 cue 15 双语完整性：`Megaspeed` → `名为 Megaspeed`。

验证：

- 完整重建 354.304 s，`verdict=pass`，V-44 PASS。
- 抽帧：第 1 页与第 2 页中文小字消失，英文要点可读；见 `docs/stabilization/evidence/c26/`（4 张前后帧 + 2 个 15 s 片段）。
- ASR 覆盖 0.897，6 条短句/专名 mismatch 为 WARN；未删除 cue 提升覆盖率。

事实/观点：第 06 页明确标注 `MY JUDGMENT`，并有 `What this is not`；未新增事实或把判断写成结论。

## 4. C-16：品牌 2D/3D

实际修复：

- 正确入口是 `film.html` → `film.js`（不是 `index.html` → `main.js`）。
- 墙面与背板改为 `paper #FBFAF7`；曝光 0.94 → 1.02；恢复地面 `#D8D1C5` 与台面层次。
- 重渲 `out/wayne-atelier-v2.mp4`（20 s / 600 帧 / 1080p30）。

Gate 3 复核：

| 标准 | 判定 |
| --- | --- |
| 品牌符号自然出现 | 部分（W 从纸板生长，但不来自角色动作） |
| 一个叙事 | 部分（角色→曲线→纸板，曲线与品牌关系弱） |
| 最后 3 秒单独成立 | 通过 |
| 无声音也能看懂 | 人工初看通过，未做正式无音轨测试 |
| 连看 3 次不烦 | 未执行 |

结论：**Gate 3 未通过**。前后帧在 `BrandIntro/gates/evidence-2026-11-10/`，逐项判定在 `BrandIntro/gates/GATE3_REVIEW_2026-11-10.md`。最终视觉签核由人决定。

## 5. C-07：05 已批准字幕

- 9 条 WARN 逐条核对：6 条是英文句子跨 cue 续行/固定搭配（`look for`、`attend to`、`point to`），规则误报；3 条是中文标点被挤到下一行（cue 18/34/60），真实排版错误。
- 只在这 3 个 cue 内重新断行，文本与时间不变；未重排全片、未删 cue、未改语义。
- V-44 规则修正：下一 cue 小写续行、当前 cue 句末标点，不再报悬空介词。
- `subtitles-qc` 05 = PASS。复核记录：`lessons/05-transformer-5min/authoring/subtitles-review-2026-11-10.md`。
- 05 已按新 SRT 重建：292.373 s，`verdict=pass`，V-44 PASS；ASR 0.992、0 mismatch。

## 6. C-28：品牌工作提交

- `84d5d5c`：`brand-desktop` 源码 + Gate 1 记录 + `.gitignore` 资产规则。
- `e611886`：`brand-intro` 源码、角色/场景资产、C-16 修正、Gate 3 复核与前后帧。
- 不提交：`out/**`、`brand-rise/**`、`env-*.png`、`character-*.png`、`*.blend1`、`film.before-c16.js`、`three.module.js` 副本。
- 分类与理由：`BrandIntro/ASSET_CLASSIFICATION.md`。
- 两目录不被生产代码引用；只被 `BrandIntro/` 与设计文档引用。

## 7. 最终全量回归

| 项 | 结果 |
| --- | --- |
| `check.ps1` | exit 0，`check ok` |
| 单测 | 六套 639：633 通过、6 跳过（CourseControl 492 / ModelingStudio 33 / ai_runtime 50 / ContentQA 25 / Manim 18 / KnowledgeStudio 21） |
| Remotion | `tsc --noEmit` exit 0 |
| 06 | 64.405 s，`verdict=pass`；V-31/V-44 PASS；ASR 0.935、0 mismatch；media-qc 9 段冻结 WARN；quality-report Q1/Q2 INCOMPLETE，`RELEASE_APPROVED=false` |
| NVDA | 354.304 s，`verdict=pass`；V-44 PASS；ASR 0.897、6 条 mismatch WARN；media-qc 19 段冻结 WARN；`VERIFY_PASS=true`，`RELEASE_APPROVED=false` |
| 05 | 292.373 s，`verdict=pass`；V-31/V-44 PASS；ASR 0.992、0 mismatch；媒体冻结 58 段 WARN |
| 交付包 | 05 55 文件、06 22 文件、NVDA 26 文件；三个 `package-verify` 均通过；06 外部声线参考已打包 |
| Git | 品牌两笔提交已入库；本轮代码与文档提交见 §10；课程内容与 `build/` 不入库 |


## 8. 问题台账终态

- VERIFIED 25：C-02、C-03、C-04、C-05、C-06、C-08、C-10、C-11、C-12、C-13、C-15、C-17、C-18、C-19、C-20、C-21、C-22、C-23、C-24、C-25、C-26、C-27、C-28、C-29、C-30。
- FIXED 4：C-01、C-07、C-09、C-14。C-07 因 01 仍有行首标点 WARN，未升 VERIFIED。
- IN_PROGRESS 1：C-16（Gate 3 未通过）。
- OPEN 0。
- C-31、C-32：均已修复并实测。


## 9. 仍需所有者决定

- C-16 Gate 3 视觉签核。
- C-25 06 新措辞的编辑签核；C-26 新闻写作与版式的编辑签核。
- 05 字幕微调是否作为正式修订。
- 06/NVDA/05 的 review / release 签核。
- 是否把 3D 片头接入品牌层（当前不接入）。

## 10. Git

- 已提交：`84d5d5c`（brand-desktop 源码）、`e611886`（brand-intro 源码与 Gate 3 复核）；本轮代码与文档提交见 `git log`。
- 课程内容与 `build/` 不入库；`lessons/` 的修改保留在本地。
