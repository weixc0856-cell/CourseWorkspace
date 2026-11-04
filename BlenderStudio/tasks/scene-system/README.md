# scene-system 验收任务

这些任务使用 `schema_version: 2`，`lesson` 统一为 `blender-scene-acceptance`，产物写入 `build/blender-scene-acceptance/`。

| 文件 | 覆盖能力 | 预期 |
| --- | --- | --- |
| `demo-scene.json` | 场景/集合/图元/材质/相机/灯光/父子/保存 | 单帧 PNG，`scene-run` 全 pass |
| `demo-animation.json` | 多帧 MP4，无动画 | 30 帧 / 1 秒 MP4 |
| `demo-animation-scene.json` | 变换、相机、灯光关键帧 | 90 帧 / 3 秒 MP4，≥13 条 F-Curve |
| `demo-modify.json` | `base_blend` 追加、复用活动相机 | 在 `scene.blend` 基础上追加对象 |
| `demo-geometry-nodes.json` | GN 位移、GN 实例散布、GN 材质输入 | 2 个 NODES 修改器 |
| `demo-text-curve.json` | `TEXT` 文字、`CURVE` 曲线、`ORTHO` 正交相机 | 4 个文字与 3 条曲线通过专项验收 |
| `invalid-*.json` | 重复 ID、非法集合根、无相机、越界输出、非法图元、未知材质、空文字、文字带图元、曲线点数不足、曲线倒角为 0、非法投影方式 | 外部与 Blender 双端均拒绝 |

## 运行

```powershell
# 单任务
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 全量契约校验
Get-ChildItem BlenderStudio/tasks/scene-system/*.json | ForEach-Object {
  uv run --project CourseControl course-control scene-validate --task $_.FullName
}
```

`demo-modify.json` 依赖先运行 `demo-scene.json` 生成的 `scene.blend`。

## 产物

```text
build/blender-scene-acceptance/
├── blender/
│   ├── scene.png / scene.blend
│   ├── animation.mp4 / animation.blend
│   ├── geometry-nodes.png / geometry-nodes.blend
│   ├── modified.png / modified.blend
│   └── manifests/<task_id>.json
└── logs/
```
