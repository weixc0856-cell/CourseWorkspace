# 收敛裁决（DECISIONS）

- 日期：2026-11-10
- 唯一完整决策记录在 `docs/DECISIONS.md`；本文件只做本轮裁决索引，不复制全文。
- 冲突处理原则：先记录裁决，再改代码；同一问题只有一个权威结论。

## 1. 本轮裁决

| 编号 | 裁决 | 影响 | 状态 |
| --- | --- | --- | --- |
| D-071 | 质量以交付为准，运动阈值只作诊断 | `beats.py`、`quality_gates.py` | 已实施 |
| D-072 | 两种生产单元、质量状态机、标准交付包 | `pipeline`、`quality`、`package` | 已实施 |
| D-073 | 配置一次解析、不可变快照、指纹进入 resume | `config_resolve.py` | 已实施 |
| D-074 | 阶段检查点与顶层 resume | `checkpoint.py`、`pipeline.py` | 已实施 |
| D-075 | Blender 任务统一入口，两代 Schema 不可混淆 | `blender_task.py` | 已实施 |
| D-076 | legacy 时间线字段必须登记，未登记即 V-43 失败 | `legacy_registry.py` | 已实施 |
| D-077 | 缺失证据必须分类，未分类即失败 | `check_evidence.py`、`evidence-decisions.yaml` | 已实施 |
| D-078 | 八类镜头能力是生产边界 | `shot-taxonomy.yaml` | 已实施 |
| D-079 | WARN 分类与统一裁决队列 | `quality.py`、`review_decisions.py` | 已实施 |
| D-080 | 外部资产进入交付包，three.js 只保留一份 | `assets.py`、`vendor.py`、`package.py` | 已实施 |
| D-081 | 探针与生产入口分离 | `RemotionStudio/src/probes/` | 已实施 |

## 2. 被取代或失效的说法

| 旧说法 | 现在 |
| --- | --- |
| "27 个独立镜头"（05） | 27 条是节拍表内部动作；生产单元是 1 个 Page 场景 |
| "QUALITY_PASS 就是质量通过" | 它只等于 `VERIFY_PASS`；`QUALITY_VERIFIED` 要求全 PASS |
| "WARN 都无所谓" | WARN 分 `human_review` 与 `blocking` |
| "阶段标记完成即可跳过" | 必须校验配置指纹、输入哈希、输出哈希 |
| "three.js 每个镜头各存一份" | 唯一 vendor 副本 + 构建时复制 |
| "Motion Canvas 需要人工导出" | 无头导出（D-054） |
| "文档引用缺失是正常的" | 必须匹配处置规则，否则检查失败 |

## 3. 未裁决事项

| 事项 | 需要谁 | 阻塞什么 |
| --- | --- | --- |
| 05 已批准 SRT 是否重排并重新验收 | 所有者 | C-07 的最终关闭 |
| 是否拆分 05 的 1,622 行 Manim 场景为 3 个可独立渲染类 | 所有者 | C-01 的镜头级增量承诺 |
| 06 标题时长、因果遮罩表述、示意矩阵 | 所有者 | C-25 |
| nvda 新闻片是否移除幻灯片中文段落 | 所有者 + 视觉验收 | C-26 |
| 3D 片头是否继续、何时过 Gate 3 | 所有者 | C-16、C-28 |
| 01/05 的 review/release 签核人 | 所有者 | `RELEASE_APPROVED` |

这些问题不由程序代答。
