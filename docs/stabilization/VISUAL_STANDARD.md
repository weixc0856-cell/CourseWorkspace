# 视觉标准（VISUAL_STANDARD）

- 日期：2026-11-10
- 关联：C-09、C-16、C-24（多配置源之外的视觉部分）、C-26
- 现行依据：`shared/design-tokens/tokens.json`、`shared/design-tokens/brand.json`、`docs/配色规范.md`、`docs/版式系统.md`、`docs/课程视觉风格指南.md`
- 状态：规范已定；3D 品牌艺术与新闻片版式仍需人工验收

## 1. 一套体系，两种媒介

2D 与 3D 不要求长得一样，但必须属于同一个视觉体系。

| 维度 | 2D（Remotion / Manim / Canvas） | 3D（Blender / Three.js） |
| --- | --- | --- |
| 背景 | `paper #FBFAF7` | 同一 `paper` 或略暗的纸面，不使用默认灰 |
| 主体 | 墨色 `ink #252A31`，单一橙色焦点 | 材质基色向 `ink` 靠拢，橙色只用于电流/重点 |
| 强调 | `orange #E8733B` 一帧一处 | 发光强度受控，不溢色 |
| 字体 | 无衬线 `Noto Sans SC / Segoe UI`；等宽 `Cascadia Mono` | 3D 文字与 2D 同字重、同字距；不做立体挤出 |
| 灯光 | 无环境光陷阱；对比度优先 | 主光 + 补光，阴影方向固定；不做无来源的轮廓光 |
| 网格 | 96 px 安全边距 | 构图投影到同一安全区 |
| 转场 | 硬切或短溶解（≤ 0.4 s） | 与 2D 同规则；不做无动机运镜 |

## 2. 镜头能力（8 类）

`shared/grammars/shot-taxonomy.yaml` 是唯一清单。每类镜头必须提供：

- 输入契约；
- 视觉目标；
- 适用与禁用场景；
- 动画规则；
- 质量检查；
- 真实样片（`SPEC.md` + `VERIFY.md`，不能有 `| fail |`）。

| 类型 | 作用 | 已验样片 |
| --- | --- | --- |
| concept | 概念与定义 | `CodeVideoStudio/shots/attention-flow` |
| mechanism | 机制与过程 | `attention-flow` |
| comparison | 对比与差异 | `attn-matrix` |
| data | 数据与证据 | `gpu-trace` |
| structure | 架构与组成 | `compute-topology` |
| transformation | 状态变化 | `primer-aging` |
| narrative | 叙事与案例 | `attn-hook` |
| summary | 总结与归纳 | `attn-recap` |

Agent 可以组合类型，不得发明未登记的能力。`course-control shot-taxonomy` 定期检查契约与样片覆盖。

## 3. 品牌

`shared/design-tokens/brand.json` 是品牌数据权威；`docs/品牌与片头片尾.md` 是行为权威。

- 片头 3.0 s：lockup + 英文单集标题；末帧保持标题卡，正片硬切。
- 课程片尾 12 s：lockup + 致谢 + CTA；新闻片尾 6 s，保留栏目与真实日期。
- 竖屏只用 `short_signature`。
- 品牌只做 `片头 → 正片 → 片尾` 线性拼接；正片是原子资产。
- 品牌帧只用英文；分类编号、中文副题、课程元数据不进入品牌画面。

**已知未完成**：`brand.json` 仍保留 `content_kinds.*.label`，而 D-070 决定移除；3D 片头背景与橙色电流未统一到 `paper`。这两项在人工 Gate 前不纳入生产默认链路。

## 4. 2D/3D 品牌 Gate

3D 片头必须依次通过：

1. Gate 1：构图与角色可读（灰盒可过）；
2. Gate 2：材质、灯光、色彩属于同一品牌体系；
3. Gate 3：完整片头在真实成片中与 2D 片尾并置不违和。

2026-11-10 复核：20 秒工作室原型已把墙面/背板改为 `paper #FBFAF7`、恢复地面层次并重渲（`out/wayne-atelier-v2.mp4`）。**Gate 3 仍未通过**：角色比例偏小，品牌 W 只在最后 1.6 s 出现，尚未与角色动作形成同一叙事。前后帧与逐项判定见 `BrandIntro/gates/GATE3_REVIEW_2026-11-10.md`。

在 Gate 3 通过前：

- 不把 3D 片头写进 `BrandIntro` 生产路径；
- 不用 3D 图替换 2D 品牌资产；
- 设计稿、失败记录与当前版本保留在 `BrandIntro/` 与 `docs/品牌片头-3D桌面戏-设计.md`。

## 5. 新闻片密度

新闻片与课程片不共用节奏标准。

| 指标 | 课程片 | 新闻片 |
| --- | --- | --- |
| 第一屏信息 | 一个概念或问题 | 一个事实 + 一个影响 |
| 幻灯片中文段落 | 允许讲稿式说明 | 不允许；中文交给字幕 |
| 每页信息增量 | 一个知识单元 | 一个事实或一个判断 |
| 最长时间停留 | 按旁白句 | 不超过 8 s 无新信息 |
| 事实/观点 | 由讲稿承担 | 画面必须区分 |

`lessons/nvda-gpu-control` 的 8 页幻灯片仍带 80–120 字中文段落。修改会改变新闻片版式，需所有者批准；在此之前不声称新闻片密度达标。

## 6. 验收

- 每类镜头至少一支 30–60 s 真实样片，人工看过并签字；样片不是封面图。
- 品牌片段单独看成片，再看与正片拼接后的完整版本。
- 检查项：构图、主体大小、连续性、字幕可读、音画同步、2D/3D 并置是否违和。
- 自动检查只能证明文件与时间轴正确；"好不好看"由人判断。
