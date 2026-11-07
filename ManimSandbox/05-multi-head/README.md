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
# 每段一次；完整命令见 docs/E6.5-成片报告.md
uv run --project CourseControl course-control narrate --workspace . `
  --lesson e6.5-multi-head --segment-id e65-b1 `
  --text-file ManimSandbox/05-multi-head/narration/b1.txt `
  --voice-ref "<VOICE_REF_WAV>" `
  --prompt-text "希望你以后能够做的比我还好呦。" `
  --out build/manim-multi-head/e6.5/narration/segments/e65-b1.wav

python ManimSandbox/05-multi-head/assemble.py
```

- 成片：`build/manim-multi-head/e6.5/final.mp4`（86.929 s）。
- 自动检查写入 `build/manim-multi-head/e6.5/manifest.json`。
