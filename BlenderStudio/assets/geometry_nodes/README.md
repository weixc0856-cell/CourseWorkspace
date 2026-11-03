# Geometry Nodes 资产库

## 文件

| 文件 | 说明 |
| --- | --- |
| `gn_library.blend` | 可复用节点组的唯一来源；由构建脚本生成，提交入库 |
| `registry.json` | 任务契约：资产 id、节点组名、版本、输入类型与范围 |
| `build_assets.py` | 在 Blender 中重建 `gn_library.blend` |

## 当前资产

| 资产 id | 节点组 | 输入 |
| --- | --- | --- |
| `gn.displace_noise` | `GN_DisplaceNoise` | `Scale`、`Strength`、`Seed` |
| `gn.scatter_cubes` | `GN_ScatterCubes` | `Density`、`Scale`、`Seed`、`Material`（可选） |

## 重建

```powershell
& "<BLENDER_EXE>" --background --factory-startup --python-exit-code 1 `
  --python BlenderStudio/assets/geometry_nodes/build_assets.py
```

构建脚本会给节点组设置 `use_fake_user = True` 并 `asset_mark()`；否则没有用户的节点组不会写入 `.blend`。

## 新增资产

1. 在 `build_assets.py` 中增加构建函数，接口命名稳定、语义明确。
2. 在 `registry.json` 增加条目：`blend`、`node_group`、`version`、`blender_min`、`inputs`（`type`、`default`、`min`、`max`、`required`）。
3. 重建资产库。
4. 增加一个 `BlenderStudio/tasks/scene-system/` 验收任务，运行 `course-control scene-run`，确认渲染与 `scene.geometry_nodes` 检查通过。
5. 更新 `docs/Blender场景任务IR-v2.md` 的资产表。

## 接口规则

- 外部只按 **Socket 名称**传参；执行时从节点组 Interface 读取 identifier，不硬编码 `Socket_1`。
- 注册表声明的类型必须与 Interface 的 `socket_type` 一致，否则执行失败。
- 资产升级时提升 `version`；破坏性改动必须同时更新注册表与验收任务。
- 实例化资产如果需要材质，显式暴露 `NodeSocketMaterial` 输入，并在节点树中 `Realize Instances → Set Material`，避免实例回落为默认白材质。
