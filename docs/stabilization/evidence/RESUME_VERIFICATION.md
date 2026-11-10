# Resume 实测记录（2026-11-10）

- 对象：`06-attention-sample`，默认 build root
- 目的：验证 Resume 不信任"阶段已标记完成"，而是校验输入、配置、输出哈希

## 1. 已生成中间产物被修改

步骤：

1. 备份 `animation/attn-hook.mp4`。
2. 截断为 1,000 字节，把 mtime 设到 1980-01-01。
3. 运行 `course-control build --lesson 06-attention-sample --resume`。

结果：

```json
{
  "reused": ["render:manim", "collect", "compose"],
  "replayed": ["render:code_video"],
  "invalid": {
    "render:code_video": ["output hash changed: animation/attn-hook.mp4"]
  }
}
```

- 构建重新捕获 `attn-hook`，输出恢复到 180,943 字节。
- 重新捕获的字节哈希与检查点记录一致，因此 `compose` 仍可复用。
- 构建 `verdict=pass`。

证据：`resume-output-tamper.json`。

## 2. 配置发生变化

步骤：

1. 在 `config/tools.yaml` 末尾追加一行注释（只改文件哈希，不改行为）。
2. 运行 `course-control build --lesson 06-attention-sample --resume`。

结果：

```json
{
  "reused": [],
  "replayed": ["render:manim", "render:code_video", "collect", "compose"],
  "invalid": {
    "render:manim": ["configuration fingerprint changed"],
    "render:code_video": ["configuration fingerprint changed"],
    "collect": ["configuration fingerprint changed"],
    "compose": ["configuration fingerprint changed"]
  }
}
```

- 所有带检查点的阶段都因配置指纹变化而重跑。
- 构建 `verdict=pass`。
- 随后恢复原 `config/tools.yaml`，再做一次收尾构建，使最终产物的配置快照与仓库配置一致。

证据：`resume-config-change.json`。

## 3. 结论

- 输出哈希变化：真实识别并重跑。
- 配置哈希变化：真实识别并重跑。
- 输入哈希变化：上一轮已由 vendor 文件变化触发（`render:code_video` 失效）。
- 三种失效都不是"阶段完成即跳过"。
