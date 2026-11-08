# Attention · 2 分钟样片（3B1B 视觉语言）

一个机制：`it` 的 query 对所有 key 打分 → 因果遮罩 → softmax → 混合 value，得到 context。

- 场景源码：`attention.py`（Manim CE 0.22，`AttentionScene`）
- 旁白：`narration/s01..s11.txt`，本地 VoxCPM2 合成
- 成片：`build/attention-3b1b/attention.mp4`（1920×1080 / 60 fps / 约 2 分钟）
- 差距分析：`docs/样片-注意力-3B1B差距与路线.md`

## 重建

```powershell
# 1. 旁白（需要 127.0.0.1:50000 的 VoxCPM2；写 build/attention-3b1b/timing.json）
python ManimSandbox/06-attention-3b1b/gen_narration.py

# 2. 画面（镜头边界读 timing.json，音画同一时钟）
cd ManimSandbox
uv run manim render -r 1920,1080 --fps 60 `
  --media_dir ../build/attention-3b1b/media `
  06-attention-3b1b/attention.py AttentionScene

# 3. 合成（回到仓库根目录）
python ManimSandbox/06-attention-3b1b/build_final.py
```

`build_final.py` 读取 `timing.json`、按时间轴铺旁白、`loudnorm`（-16 LUFS / -1 dBTP），再与无声画面混流。

口播模式（`gen_narration.py`）：

- 默认 `NARRATION_MODE=hifi`：`prompt_wav` + `prompt_text`，音色最接近参考，风格指令无效。
- `NARRATION_MODE=controllable`：只传 `reference_wav`，文本前的括号指令生效，用于下一步表达控制 A/B：

```powershell
$env:NARRATION_MODE="controllable"
$env:NARRATION_STYLE="Speak in a natural, calm and clear explanatory style. Conversational pace, restrained emphasis."
python ManimSandbox/06-attention-3b1b/gen_narration.py
```

改模式或台词后先删除 `build/attention-3b1b/audio/` 下对应的 `.wav`，否则脚本会复用旧音频。

## 约定

- 只用 uv，不装全局依赖。
- 产物只写 `build/attention-3b1b/`。
- 旁白文本和镜头切分是同一份时间轴；改台词后必须重跑第 1 步，否则音画会错位。
