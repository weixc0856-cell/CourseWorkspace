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
