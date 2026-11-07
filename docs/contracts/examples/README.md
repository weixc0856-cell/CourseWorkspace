# 契约示例 JSON

本目录是 `docs/课程生产统一契约V1.md` 的结构示例，**不是验收证据**。

- 所有示例只用于说明字段、类型与关系，尚未接入运行时。
- `fps` 一律是 `{fps_num, fps_den}` 有理数；示例使用 30/1，但契约不写死 30。
- 标为 `0000…`、`1111…` 的哈希与 `bytes: 0` 是占位值；不要当作真实文件校验结果。
- `render.manifest.json` 的 `checks` 故意写成 `not_run`，表示“设计示例，不是通过记录”。
- `e6.render.manifest.v1.json` 使用 `build/manim-transformer/e6/` 的真实媒体哈希，`source` 为 `null`（legacy 适配）；V0 `manifest.json` 的人工 `checks` 只放在 `legacy.manual_checks`，且 `manual_checks_trusted: false`。实际 `e6-adapt` 会生成自动检查；示例中的 `checks` 为空，表示不是验收记录。
- E6 当前只有混合后的 `narration.wav`；`narration.spec.json` 中的参考音与分段 WAV 路径都是规划路径，不是现有文件。
- `shot.spec.session.json` 是 Session 镜头的结构示例，数值与哈希为占位值。

实现阶段会用 Pydantic 模型和 JSON Schema 重新校验这些示例；届时不占位的示例才进入测试。
