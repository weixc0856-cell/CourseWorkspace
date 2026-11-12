# 最终验收报告（2026-11-10 收尾轮）

- 范围：C-01～C-32 遗留项、06 内容修正、NVDA 密度、品牌 Gate 3、05 字幕复核、品牌资产提交
- 原则：工程通过、内容通过、视觉通过、交付包通过、发布批准是五个独立状态，不互相替代

## 0. 状态总表

| 状态 | 结果 | 依据 |
| --- | --- | --- |
| `ENGINEERING_VERIFIED` | **true** | `check.ps1` exit 0；六套单测；06 / NVDA / 05 真实构建；配置、resume、字幕、资产、vendor 检查 |
| `CONTENT_VERIFIED` | **false（机器一致性通过，编辑签核未完成）** | C-25 旁白/字幕/画面已一致；C-26 事实/判断已分开；但措辞与新闻写作仍由所有者最终确认 |
| `VISUAL_VERIFIED` | **false（C-16 已 DEFERRED，不阻塞 V1）** | 片头概念/角色未成熟，所有者决定暂缓；保留源码、资产与 Gate 3 证据 |
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

验证到的内容（本轮补做两项真实注入，见 `docs/<内容根>/archive/stabilization-evidence/RESUME_VERIFICATION.md`）：

- 输入哈希：新增 vendor 文件使 code_video 检查点失效。
- 输出哈希：截断 `animation/attn-hook.mp4` 并改旧 mtime 后，`--resume` 记录 `output hash changed: animation/attn-hook.mp4`，重跑 code_video 并恢复为相同哈希，compose 复用。
- 配置指纹：向 `config/tools.yaml` 加一行注释后，`--resume` 将 manim/code_video/collect/compose 全部标记 `configuration fingerprint changed` 并重跑；恢复配置后再构建一次，最终快照与配置一致。
- 字幕变化：NVDA 的 `--resume` 记录显示字幕输入使 capture/compose/burn 失效；已收窄检查点输入范围，字幕只失效 consuming stages。

### 1.3 交付包

- 06：28 个文件；外部声线参考打包到 `assets/external/719ce803-my_voice_clean_v1.wav`，`package-verify` 通过。
- NVDA：27 个文件；`package-verify` 通过。
- 05：55 个文件；`referenced_assets` 记录 BGM 与声线参考的 `asset_id`/SHA-256。BGM 是**重新混音的外部依赖，不是播放必需资产**：`course-video-mixed.mp4` 已包含 BGM；源文件记录 `license_status=public_domain`、`attribution`、`acquisition=resolve under config/local-paths.yaml bgm_root`，换机可按根目录放置并用哈希复核。

### 1.4 三个“通过”的含义

| 输出 | 只代表 |
| --- | --- |
| `check.ps1` = check ok | 工程回归、契约、单测、类型检查通过 |
| `build-report.verdict=pass` | 本次构建的阶段与检查没有 fail；不代表作品可发布 |
| `package-verify` = package ok | 包内文件与 manifest 哈希一致；不代表内容或视觉合格 |

### 1.5 本轮端到端范围

06 是**单一 65.5 秒课程**的完整构建（config → validate → render → collect → compose → verify），不是 20 分钟长课 01 的完整生产，也不是多课程批量生产。NVDA 是 354 秒新闻片的完整构建。两者都不等于“所有课程类型已验收”。

## 2. C-25：06 内容矛盾

| 项 | 修改 |
| --- | --- |
| 标题 | `Attention in Ninety Seconds` → `How Attention Works in About a Minute`；中文 `九十秒看懂注意力` → `一分钟看懂注意力`；`slides.md` 同步 |
| 因果遮罩 | 旁白 s005、`lecture_notes.md`、SRT cue 11 改为“解码器里的注意力，能看当前和之前的位置，不能看未来” |
| 画面 | `attn-mask` 标题改为“解码器：能看当前和之前”，副题“不能看未来；未来位置被遮住”；SPEC 同步 |
| 时间轴 | s005 6.88 → 10.24 s；全片 62.16 → 65.533 s；production/beats/SRT 重新定时 |

验证：

- 06 重建 `verdict=pass`，V-14 65.533 s，V-31/V-44 PASS。
- ASR 覆盖 0.935，0 cue mismatch。
- 画面帧确认“能看当前和之前 / 不能看未来”与字幕一致；前后帧在 `docs/<内容根>/archive/stabilization-evidence/c25/`。
- 原始版本保存在 `lessons/06-attention-sample/authoring/original-2026-11-10/`；审批记录通过 `author-accept` 写入，措辞的最终编辑签核仍需所有者确认。

## 3. C-26：NVDA 新闻片密度

修改：

- 删除 8 页 `<div class="zh-sub">` 中文段落；中文由字幕承担。
- 未改旁白、page 时长、镜头顺序或语速。
- 修复 cue 15 双语完整性：`Megaspeed` → `名为 Megaspeed`。

验证：

- 完整重建 354.304 s，`verdict=pass`，V-44 PASS。
- 6 条 ASR mismatch 已逐条分类：3 条日期/专名识别差异保留，3 条真实时间轴提前已重定时（cue 80–84、111–116）。重跑后 ASR 0.919、3 条 mismatch。
- 抽帧：第 1 页与第 2 页中文小字消失，英文要点可读；见 `docs/<内容根>/archive/stabilization-evidence/c26/`（4 张前后帧、2 个 15 s 片段、编辑审阅记录）。
- 未删除 cue 提升覆盖率。

事实/观点：第 06 页明确标注 `MY JUDGMENT`，并有 `What this is not`；未新增事实或把判断写成结论。

## 4. C-16：品牌 2D/3D（DEFERRED）

所有者决定：当前视觉概念与 3D 角色设计不成熟，片头暂缓，不在现有方案上继续打补丁。

- 保留 `BrandIntro/` 设计记录、`CodeVideoStudio/shots/brand-intro` 源码、角色资产、Gate 3 前后帧。
- 本轮已完成的实际修正保留：`film.js` 墙面/背板改 `paper`、曝光 1.02、恢复地面层次，重渲 `wayne-atelier-v2.mp4`。
- Gate 3 结论仍为未通过：角色比例偏小、品牌 W 与角色动作未形成同一叙事。见 `BrandIntro/gates/GATE3_REVIEW_2026-11-10.md`。
- 片头不进入生产默认链路，不阻塞 V1；后续独立重新设计。

## 5. C-07：05 已批准字幕

- 9 条 WARN 逐条核对：6 条是英文句子跨 cue 续行/固定搭配（`look for`、`attend to`、`point to`），规则误报；3 条是中文标点被挤到下一行（cue 18/34/60），真实排版错误。
- 只在这 3 个 cue 内重新断行，文本与时间不变；未重排全片、未删 cue、未改语义。
- V-44 规则修正：下一 cue 小写续行、当前 cue 句末标点，不再报悬空介词。
- `subtitles-qc` 05 = PASS。复核记录：`lessons/05-transformer-5min/authoring/subtitles-review-2026-11-10.md`。
- 05 已按新 SRT 重建：292.373 s，`verdict=pass`，V-44 PASS；ASR 0.992、0 mismatch。
- 01 的 18 条“行首标点”WARN 单独记录在 `docs/<内容根>/archive/stabilization-evidence/c07/01-review.md`，不与 05 修复混为同一状态。

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
| 单测 | 六套 647：641 通过、6 跳过（CourseControl 494 / ModelingStudio 33 / ai_runtime 50 / ContentQA 25 / Manim 18 / KnowledgeStudio 27） |
| Remotion | `tsc --noEmit` exit 0 |
| 06 | 65.533 s，`verdict=pass`；V-31/V-44 PASS；ASR 0.935、0 mismatch；media-qc 9 段冻结 WARN；quality-report Q1/Q2 INCOMPLETE，`RELEASE_APPROVED=false` |
| NVDA | 354.304 s，`verdict=pass`；V-44 PASS；ASR 0.919、3 条 mismatch WARN；media-qc 19 段冻结 WARN；`VERIFY_PASS=true`，`RELEASE_APPROVED=false` |
| 05 | 292.373 s，`verdict=pass`；V-31/V-44 PASS；ASR 0.992、0 mismatch；媒体冻结 58 段 WARN |
| 交付包 | 05 55 文件、06 28 文件、NVDA 27 文件；三个 `package-verify` 均通过；06 外部声线参考已打包 |
| Git | 本轮收尾提交见 §10；课程内容与 `build/` 不入库 |


## 8. 问题台账终态

- VERIFIED 25：C-02、C-03、C-04、C-05、C-06、C-08、C-10、C-11、C-12、C-13、C-15、C-17、C-18、C-19、C-20、C-21、C-22、C-23、C-24、C-25、C-26、C-27、C-28、C-29、C-30。
- FIXED 4：C-01、C-07、C-09、C-14。C-07 因 01 仍有行首标点 WARN，未升 VERIFIED。
- DEFERRED 1：C-16（所有者决定暂缓片头，不阻塞 V1）。
- OPEN 0。
- C-31、C-32：均已修复并实测。


## 9. 仍需所有者决定

- C-16 已 DEFERRED，无需本轮签核；后续独立项目重启。
- C-25 06 新措辞的编辑签核；C-26 新闻写作与版式的编辑签核。
- 05 字幕微调是否作为正式修订。
- 06/NVDA/05 的 review / release 签核。
- 是否把 3D 片头接入品牌层（当前不接入）。

## 10. Git

- 本轮提交：
  - `84d5d5c` brand-desktop 源码与资产规则
  - `e611886` brand-intro 源码与 Gate 3 复核
  - `2f8869f` C-25/C-26/C-07、检查点粒度、验收报告
  - `6300b28` 最终提交哈希记录
  - `eca19a4` 删除品牌试验渲染与备份
  - `a4f0bad` C-16 DEFERRED、06 因果措辞、NVDA 审阅、Resume 实测
- 推送状态见本轮结束时的 `git status -sb`；课程内容与 `build/` 不入库，`lessons/` 修改保留在本地。
