# lessons/ — 本地课程内容（不入库）

本目录存放真实课程内容，**不进入远程仓库**。仓库只保留工作流、契约、夹具与文档。

## 本地目录结构

```text
lessons/<slug>/
├── lesson.yaml          # 课程配置（必需）
├── storyboard.yaml      # 镜头表（必需）
├── slides.md            # 观众视图（必需）
├── lecture_notes.md     # 讲师手册，四要素（必需）
├── outline.md           # 大纲（可选）
├── assets/              # 课程素材（可选）
├── subtitles.srt        # 字幕（可选）
└── delivery-checklist.md  # 本课交付状态（本地记录，可选）
```

## 远程仓库里保留什么

- 本文件（契约说明）。
- `CourseControl/tests/fixtures/lesson-*`：合成测试夹具，不是真实课程。
- `BlenderStudio/tasks/lesson-*`、`BlenderStudio/scenes/lesson-*`：渲染夹具。

## 提示

- `git status` 不会显示本目录下的课程文件；这是预期行为。
- 新建课程时只需创建 `lessons/<slug>/` 并按 `docs/课件制作总指导.md` 与 `docs/PRD.md` FR-01 填写。
- 课程备份请另存（本目录与 `build/` 都不在版本控制内）。

## R1 authoring 目录（2026-11-07）

```text
lessons/<slug>/
├── authoring/
│   ├── sources.yaml           # 来源清单（URL/MD/TXT，sha256、抓取时间）
│   ├── sources/S*.md          # 来源正文
│   ├── source-digest.{json,md}# 稳定引用 S1-3.2
│   ├── brief.{json,md}        # 课程 brief / 学习目标
│   ├── outline.{json,md}      # 大纲与页时长
│   ├── narration.script.{json,md}  # 英文带情绪口播稿
│   └── approval.json          # 人工批准（sha256）
├── outline.md                 # 正式大纲（content.outline）
└── subtitles.srt              # 正式双语字幕（subtitles-accept 写入）
```

- AI 候选先写 `build/<slug>/authoring/candidates/`；`course-control author-accept` 后才进入本目录。
- `narration.script.json` 里的 `style` 只给 TTS，不进入正文或字幕。
- 时长以 `lesson.yaml.duration` 与实测旁白为准；页面预算只作计划值。
