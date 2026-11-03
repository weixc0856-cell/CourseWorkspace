# Manim Sandbox

**备选动画引擎。** Manim Community 0.22 + Python 3.12，只在需要坐标系连续变换、空间投影、微积分曲线这类"硬核几何"时启用。日常的盒子箭头流程请用 [../MotionStudio](../MotionStudio)。

## 什么时候来这里

- 向量投影、旋转、特征空间、线性变换的几何过程
- 对数律速度剖面、曲率、相图、复变映射这类需要精确数学坐标的图
- 需要 LaTeX 公式排版（`MathTex`，需 `dvisvgm` 可用）

如果动画主体是"若干卡片按顺序流动"，留在 Motion Studio，不要在这里重搭一遍。

## 环境

- Python 3.12（`.python-version` 固定）
- 依赖管理：**只用 `uv`**，锁定 `manim==0.22.0`
- 本仓 `.venv/`，不装 pip、不用全局 Python、不改 PATH

首次：

```powershell
cd CourseWorkspace\ManimSandbox
uv sync
```

本机已装 FFmpeg 8.1 与 MiKTeX，Manim 可直接出片；`MathTex` 若报 LaTeX 错误，多半是 `dvisvgm` 缺失，改用 `Text` + Unicode。

## 日常使用

```powershell
# 低清预览，-p 渲染完自动播放
uv run manim -pql 01-transformer-demo/dot_product.py DotProduct

# 确认画面后出 1080p
uv run manim -qh 01-transformer-demo/dot_product.py DotProduct
```

产物：`media/videos/<脚本名>/<画质目录>/<场景类名>.mp4`，例如 `media/videos/dot_product/1080p60/DotProduct.mp4`。

`media/` 只作为手动试渲染缓存，不是构建产物目录。

## 构建集成

CourseControl 的 `render:manim` 会以 1920×1080 / 30 fps 渲染到构建目录：

```powershell
uv run manim render -r 1920,1080 --fps 30 `
  --media_dir ..\build\<slug>\tmp\manim-media `
  <slug>/<scene>.py <SceneClass>
```

渲染完成后把 `<SceneClass>.mp4` 复制到：

```text
build/<slug>/animation/<scene-stem>.mp4
```

注意：

- 不要用 `-ql` 出构建片，它会产生 854×480，验收会因分辨率不一致失败。
- `storyboard.yaml` 的 Manim 场景写成 `<slug>/<file>.py::<ClassName>`。
- 构建由 `.\scripts\build-lesson.ps1 -Lesson <slug>` 触发；手动渲染仍可用 `media/`。

需要真实 3D 时用 [../BlenderStudio](../BlenderStudio)。

## 目录结构

```text
ManimSandbox/
├── .venv/                        # 本地虚拟环境（不入库）
├── .python-version               # 固定 3.12
├── pyproject.toml                # 依赖来源
├── uv.lock                       # 可复现解析结果
├── requirements.txt              # uv export 生成的只读快照
├── 01-transformer-demo/          # 目录名 = 课件 lesson slug
│   ├── test_demo.py              # 环境自检：橙白配色
│   └── dot_product.py            # 点积与投影
└── media/                        # 渲染产物与缓存（不入库）
```

## 约定

- **只用 uv**：`.venv` 里没有 pip；加依赖用 `uv add <pkg>`
- **配色与课件一致**：场景顶部固定 `MK_ORANGE / MK_TEXT / MK_MUTED / MK_BORDER` 与白底
- **屏幕上只出现英文**；中文交给幻灯片
- **单个机制 5~20 秒**，超出先拆分
- **不提交产物**：`media/`、`*.mp4`、`*.png`、`*.log` 已在 `.gitignore`
- **不嵌入幻灯片**：产出是独立 MP4，进剪辑软件，不写 `<video>`
