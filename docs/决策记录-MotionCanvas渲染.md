# 决策记录：Motion Canvas 渲染

- **日期**：2026-11-01
- **阶段**：R4
- **环境**：Motion Canvas `3.17.2`、Node `v24.14.1`

## 背景

R0 审计确认 Motion Canvas 3.17.2 没有 CLI 渲染入口：

- `MotionStudio/node_modules/.bin` 只有 `vite`；
- `@motion-canvas/vite-plugin` 只导出 `lib/index.js`，没有 `bin`；
- 官方导出依赖编辑器 UI 的 RENDER 按钮。

R4 的一键构建必须先决定如何处理该缺口。

## 备选方案

| 方案 | 做法 | 状态 |
| --- | --- | --- |
| A. 浏览器驱动 | Playwright 打开 `localhost:5173`，操作 RENDER 按钮 | 未采用。依赖 UI 结构，版本升级易碎 |
| B. 自建 headless exporter | 用 Chromium 直接调用渲染 API | 未采用。需要逆向内部 API，维护成本高 |
| C. 人工导出 + 校验（基线） | 用户在编辑器导出 MP4，控制层校验、收集、计时 | **采用** |

## 决定

R4 采用 **C**。

- 人工导出路径：`build/<slug>/animation/<scene-stem>.mp4`。
- 命名来自 `storyboard.scene` 的文件名，例如 `gui_vs_cli_paths.tsx` → `gui_vs_cli_paths.mp4`。
- 所有文件存在且 ffprobe 通过 → `render:motion_canvas = pass`。
- 缺失且 `lesson.yaml` 的 `build.allow_manual_animation_export=true` → `skipped`，原因 `manual_export_required`，最终 `verdict=incomplete`。
- 缺失且该开关为 `false` → `fail`。
- 不允许用截图拼帧或伪造文件冒充导出结果。

## 后果

- 纯 Motion Canvas 课程在人工导出前无法得到 `verdict=pass`；这是有意设计，避免虚假通过。
- `build-report.json` 会明确写出 `manual_export_required` 与缺失文件。
- A/B 作为后续升级路径，不在 R4/R5 实现；若要实现，先单独验证并更新本记录。

## 证据

- R0 审计：`MotionStudio/node_modules/.bin` 无 Motion Canvas 入口；`@motion-canvas/vite-plugin` 无 `bin`。
- R4 夹具：`render:motion_canvas = not_applicable`；真实课程 `01-shell-for-ai-era` 在未导出时得到 `skipped` / `incomplete`。
