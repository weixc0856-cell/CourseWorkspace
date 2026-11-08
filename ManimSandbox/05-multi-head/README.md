# E6.5 Multi-Head

- `multi_head_math.py`：两头算例的唯一数据源；纯标准库，不依赖 numpy/Manim。
- `verify_math.py`：独立计算 Q/K/V、scores、softmax、context、concat、W_O，并写 JSON 报告。

```powershell
python ManimSandbox/05-multi-head/verify_math.py --output build/manim-multi-head/e6.5/math-report.json
```

- 任何维度、行和、拼接布局或教学焦点检查失败时 exit 1。
- 报告写入 `build/`，不入库。
- 该脚本通过后才进入 `MultiHeadScene` 编码。

## 视觉场景

```powershell
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-multi-head/e6.5/media `
  ManimSandbox/05-multi-head/multi_head.py MultiHeadScene
```

- `MultiHeadScene` 只负责排版与动画，所有矩阵和数值来自 `multi_head_math.py`。

## 旁白与成片

```powershell
# 每段一次；完整命令见本地归档 docs/archive/E6.5/E6.5-成片报告.md（不入库）
uv run --project CourseControl course-control narrate --workspace . `
  --lesson e6.5-multi-head --segment-id e65-b1 `
  --text-file ManimSandbox/05-multi-head/narration/b1.txt `
  --voice-ref "<VOICE_REF_WAV>" `
  --prompt-text "<VOICE_PROMPT_TEXT>" `
  --out build/manim-multi-head/e6.5/narration/segments/e65-b1.wav

python ManimSandbox/05-multi-head/assemble.py
```

- 成片：`build/manim-multi-head/e6.5/final.mp4`（86.929 s）。
- 自动检查写入 `build/manim-multi-head/e6.5/manifest.json`。

## 轨道归属

E6.5 是 **standalone render track**，不在 `lessons/` 下，因为它没有作者维护的
`lesson.yaml` / `storyboard.yaml` / 双文件正文。`e65-adapt` 生成 V1 契约时
`source.lesson_spec=null`，但仍提供 `TimelineSpec`、`NarrationSpec` 与
`RenderManifest`；后续若作者补齐课程文件，再按 V1-E 接入主链。
