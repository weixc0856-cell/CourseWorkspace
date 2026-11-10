# 最终架构（ARCHITECTURE_FINAL）

- 日期：2026-11-10
- 关联：C-01、C-13、C-14、C-17、C-18、C-24、C-30
- 状态：现行；与 `docs/ARCHITECTURE.md` 一致，本文件只固定本轮收敛后的边界

## 1. 权威链

```text
Lesson (lesson.yaml)
  │  课程、时长、引擎、字幕与音频策略
  ▼
Page (slides.md + lecture_notes.md)
  │  已批准的知识内容、讲解顺序
  ▼
Scene / Storyboard (storyboard.yaml 或 production.yaml)
  │  Page 级或 Shot 级的可渲染单元
  ▼
Shot (ShotSpec / ProductionShot)
  │  动画参数、素材、时间轴
  ▼
Renderer (Manim / CodeVideo / Motion Canvas / Blender / Remotion)
  │
  ▼
Timeline (shots.json → timeline.spec.json) → Video
```

| 对象 | 权威内容 | 不是权威 |
| --- | --- | --- |
| Page | 知识内容、文案、顺序 | 导演计划、节拍表 |
| Scene/Storyboard | 可渲染单元与页面映射 | 节拍表内部动作 |
| Shot | 动画参数、素材、时间轴 | `shots.json`（生成物） |
| Renderer | 实际像素 | 课程内容 |

导演可以重新设计视觉表达，不能修改已批准的知识内容。内容变更回到 Page 层并重新批准。

## 2. 模式与单元

| `compose.mode` | 生产单元 | 权威文件 | 构建读取 |
| --- | --- | --- | --- |
| `deck` / `scene` / `recording` | Page | `storyboard.yaml` | `build.storyboard_source` |
| `shots` | Shot | `authoring/production.yaml` | synthetic storyboard |

每门课在 `lesson.yaml.build.storyboard_source` 显式声明 `storyboard` 或 `director`。CLI 的 `--storyboard-source` 只在需要临时覆盖时使用。

## 3. 模块职责

| 模块 | 职责 | 不做什么 |
| --- | --- | --- |
| `CourseControl` | 契约、调度、配置快照、检查点、时间线、报告 | 不改课程正文；不判断内容正确性 |
| `CourseControl/config_resolve` | 一次解析全部配置并生成指纹 | 不执行渲染 |
| `CourseControl/checkpoint` | 阶段检查点与 resume | 不决定课程内容 |
| `CourseControl/director` | 章节/镜头/引擎/旁白计划 | 不写场景代码、不渲染 |
| `CourseControl/producer` | 订单、授权、用量、交付清单、增量指纹 | 不读密钥、不自动发布 |
| `CourseControl/package` | 标准交付包、哈希、外部资产打包 | 不渲染、不转码 |
| `CourseControl/quality` | 五维质量、警告分类、发布状态 | 不替代人工签核 |
| `CourseSlides` | 加载课程为 Reveal 页面 | 不写 `build/` |
| `MotionStudio` | 动画场景源码与无头导出 | 不做最终合成 |
| `ManimSandbox` | 数学动画 | 不进入主调度 |
| `BlenderStudio` | v1 课程任务、v2 场景 IR | 不读 `lesson.yaml` |
| `RemotionStudio` | 截图、staging、合成、字幕/旁白 | 不做时间线推导 |
| `ModelingStudio` | 图片→分析→规划→脚本→Blender→验收 | 不写 `lessons/` 与课程 `build/` |
| `ContentQA` | 候选审查意见 | 不改课程、不影响 verdict |
| `KnowledgeStudio` | 拆页、索引、检索、引用 | 不生成课程内容、不判断真伪 |
| `shared/ai_runtime` | 本地服务生命周期、跨进程锁、任务记录、远程回退 | 不决定课程内容 |

## 4. Blender 两代 Schema

| 版本 | 位置 | 用途 | 入口 |
| --- | --- | --- | --- |
| v1 | `BlenderStudio/tasks/<lesson>/*.json` | 课程镜头：渲染已有 `.blend` | `blender_task.load_blender_task` |
| v2 | `BlenderStudio/tasks/scene-system/*.json` | 场景 IR：从结构化描述构建场景 | 同一加载器分派 + `scene-run` |

- 未知 `schema_version` 直接失败并列出支持版本。
- v1 未知字段拒绝，输出必须在 `build/<lesson>/blender/`。
- v2 仍用于 POC 与场景验证，不进入课程默认链路，除非课程显式引用。
- 不新增第三套 Blender 任务格式。

## 5. 时间线桥接

`collect` 同时写 `shots.json` 与 `contracts/timeline.spec.json`。V1 时间线中的 `legacy_*` 字段是桥接层：

- 每个字段在 `legacy_registry.py` 登记消费者、替代字段与退出目标；
- 新增未登记字段由 V-43 判失败；
- 退出顺序：先把 Remotion 的读取迁到 V1 字段，再删除桥接，最后删除字段；
- 当前没有第二套业务逻辑，只有一份可枚举的视图。

## 6. 渲染与合成

- 适配器统一 `verify_media`：分辨率、帧率、时长。
- CodeVideo 额外检查 codec、pix_fmt、音轨、黑帧、冻结。
- CodeVideo 使用唯一 `CodeVideoStudio/vendor/three/three.module.js`，构建时复制到镜头目录。
- Remotion 生产入口 `src/index.ts` 只注册生产 composition；探针在 `src/probes/index.ts`。
- 合成超时按课程时长解析；同一课程单 build 锁。

## 7. 不增加的东西

- 不新增第七种时间/镜头表示。
- 不新增第二个配置层或第二套质量状态。
- 不新增渲染后端；先修现有四条路径的验收深度。
- 不把 POC（IRC v2 场景、3D 片头、VideoZero）并入生产默认链路。
