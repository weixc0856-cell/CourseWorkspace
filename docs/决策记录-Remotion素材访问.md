# 决策记录：Remotion 素材访问

- **日期**：2026-11-01
- **阶段**：R3
- **环境**：Remotion `4.0.539`、Node `v24.14.1`、Playwright `1.64.1`（Chrome channel）

## 结论

采用 **B. staging**：渲染前把 `build/<lesson>/` 中需要的素材复制到 `RemotionStudio/public/staging/<lesson>/`，组件统一用 `staticFile('staging/<lesson>/<source>')` 引用；渲染结束后由控制层清理 `public/staging/`。

不使用 `file://`、绝对路径或开发服务器路径直接引用 `build/` 外部文件。

## 实测

| 用例 | 输入 | 结果 |
| --- | --- | --- |
| 绝对路径图片 | `<WORKSPACE>/build/01-shell-for-ai-era/slides/slide-001.png` | **失败**，退出码 1。Remotion 将其规范化为 `file://`，Chromium 报 `Not allowed to load local resource`，最终报 `Error loading image with src: file:///...` |
| `file://` 图片 | `file:///.../slide-001.png` | **失败**，退出码 1，同上 |
| staging 图片 | `staticFile('staging/01-shell-for-ai-era/slides/slide-001.png')` | **通过**，退出码 0，输出 1920×1080 PNG |
| staging 视频 | `staticFile('staging/01-shell-for-ai-era/blender/smoke.mp4')` | **通过**，退出码 0，输出 1920×1080 PNG |
| 中文 + 空格路径 | `staticFile('staging/01-shell-for-ai-era/slides/中文 截图.png')` | **通过**，退出码 0，与同源英文路径输出哈希一致 |

探针证据为一次性产物，提交前已清理；结果见上表。需要复现时重新创建探针文件并运行 `AccessProbe`。

## 实现约束

1. `stage-assets.mjs` 以 `shots.json` 为唯一清单，复制 `shots[].source`、`narration.path`、`subtitles.path`；重复来源只复制一次。
2. 目标目录固定为 `RemotionStudio/public/staging/<lesson>/`，保持 `build/<lesson>/` 内的相对路径不变。
3. `public/staging/` 已加入 `RemotionStudio/.gitignore`，不进入 Git。
4. 组件不接收绝对路径；所有素材路径都相对 `build/<lesson>/`，由 staging 统一映射。
5. 渲染失败时 staging 目录保留用于排查；成功构建后由控制层清理（R4 实现）。
6. 中文与空格路径不需要额外转义；`staticFile` 已正确处理，但调用方必须用参数数组，不拼 shell 字符串。

## 影响

- R3 的 `CourseVideo` 使用 `staticFile(stagingPath(lesson, source))`。
- R4 的 `compose` 阶段在调用 Remotion 前执行 staging，并在成功后清理。
- R5 的产物校验仍以 `build/<lesson>/` 为准，`public/staging/` 不是交付物。
