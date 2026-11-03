# Blender 任务目录

两代任务 Schema 并存，用途不同，不要混用。

| 目录 | Schema | 用途 | 入口 |
| --- | --- | --- | --- |
| `<lesson>/` | v1 | 课程流水线的最小渲染任务：`output`、`format`、`resolution`、`fps`、`frames`、可选 `blend` | `course-control build` 的 `render:blender` 阶段；`scripts/blender-render.ps1` |
| `scene-system/` | v2 | 完整场景描述：对象、材质、相机、灯光、Geometry Nodes、动画 | `course-control scene-run` / `scene-validate` |
| `../ModelingStudio/tasks/` | v2 | 建模夹具场景（如 `reference-assembly.json`） | `course-control scene-run` |

## v1 说明

v1 没有独立场景系统，只配置渲染参数；`render_common.py` 会构建一个固定的程序化场景或打开指定 `.blend`。
保留 v1 是为了课程夹具 `lesson-smoke` / `lesson-blender-only` 的稳定接口。

`01-shell-for-ai-era/` 下的 v1 任务属于历史夹具：

- `still.json`、`cycles-still.json`：渲染入口冒烟；
- `invalid-*.json`：负例（缺输出、越界、非法分辨率）；
- `timeout-test.json`：超时行为；
- `中文 任务.json`：非 ASCII 文件名编码检查。

该课程现在只使用 Motion Canvas，这些任务不参与课程构建。

## v2 说明

契约见 `docs/Blender场景任务IR-v2.md`，Schema 为 `shared/schemas/blender-scene-task.schema.json`。
`scene-system/README.md` 列出 5 个合法 demo 与 6 个非法夹具；`scripts/check-scene-system.ps1` 负责校验。
