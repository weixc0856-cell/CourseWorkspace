# 本地图像生成（FLUX.3 / ComfyUI）

日期：2026-11-11
引擎：`D:\Local-Drama-Studio\runtime\ComfyUI`（本机，不入库），端口 8188
模型：FLUX.3 Klein GGUF Q4_K_M + Qwen3-VL 4B 文本编码器 + FLUX VAE
工作流：`D:\Local-Drama-Studio\workflows\flux3_t2i_api.json`

## 1. 能力边界（硬约束）

- **只生成静态图像。** FLUX.3 是图像扩散模型，**不能生成视频**。本机不得通过它产出视频、视频帧序列或动态素材；它的产物只能是单张 PNG。
- **图生视频写死禁用（配置原因）。** 本机不启用 Wan2.2 I2V 或任何图生视频能力：配置层面不可用，不得调用、不得用其产出镜头。`D:/Local-Drama-Studio/workflows/r0_wan_i2v_api.json` 只作为上游项目的历史工作流存在，本项目不接入。
- 动态画面只允许由 Blender（2.5D 分层绑定 / 镜头与粒子）或 Remotion（静帧运镜）对静帧制作。
- 视频仍由现有链路产出：Blender 渲染 / Remotion 合成 / FFmpeg 编码。需要"动起来"时，对本机生成的静帧做运镜（Ken Burns）或 2.5D 平板动画，而不是让 FLUX 生成动态画面。
- 生成图是**候选素材**，不是成片。必须人工检查构图、手部、文字伪影后再使用；符合「AI 输出不等于已完成」。
- 只用于内部生产素材，不把生成图直接拼进 `slides.md`、`lecture_notes.md` 等用户正文。
- 单张约占满 A750 数分钟。同一时间只跑一个 GPU 任务，不与 GPU 模式 LLM 并发。

## 2. 服务契约

- 端口：**8188**，本机唯一的 ComfyUI 实例。
- 启停（谁启动谁停止，空闲时释放端口）：

```powershell
D:\Local-Drama-Studio\scripts\start.ps1    # 启动并等待 /system_stats 就绪
D:\Local-Drama-Studio\scripts\stop.ps1     # 只杀 ComfyUI 进程树
```

- 模型路径由 ComfyUI 的 `extra_model_paths.yaml` 映射到 `D:\AI\models`，不要复制权重到项目里。
- 工作流节点：`UnetLoaderGGUF`（`flux3\flux-3-image-klein-Q4_K_M.gguf`）→ `CLIPLoader`（`qwen3vl_4b_int8_convrot.safetensors`，type `flux3`，device cpu）→ `EmptyFlux2LatentImage` → `KSampler`（`er_sde` / `simple`，16 步，cfg 1.0）→ `VAEDecode` → `SaveImage`。

## 3. 调用方式

1. `POST http://127.0.0.1:8188/prompt`，`prompt` 为填好占位符的 API 工作流 JSON：`positive_prompt / width / height / seed / steps / cfg / filename_prefix`。
2. 轮询 `GET /history/<prompt_id>` 直到出现 outputs。
3. 用 `GET /view?filename=...&subfolder=...&type=output` 下载 PNG。

本机进程必须**绕过系统代理**：用 `curl.exe`，或 Python `urllib.request.ProxyHandler({})`、`httpx(trust_env=False)`。

实测（2026-11-11，A750）：640×960、16 步、cfg 1.0 约 110–150 秒一张。

## 4. 提示词与产出质量

- FLUX.3 会在画面里自生成文字（含书法字）。提示词末尾必须写 `no text`；负面提示词只有辅助作用（cfg 1.0 时影响很小）。
- 构图与留白约束不稳，按 3–5 张一批出图再挑，不要拿第一张就用。
- 角色一致性：固定 seed、重复同一段角色描述。换姿势等于重新设计，不能当作同一角色的连续帧。
- 产出放 `build/<slug>/art/`（临时区）。需要透明背景时做抠图，再进入 Blender 平板或 Remotion 运镜。

## 5. 与现有链路的关系

```text
FLUX.3 静帧 → 抠图 → Blender 2.5D 平板（浮沉/视差/热气）或 Remotion 静帧运镜 → 成片
```

- 2.5D 做法：立绘贴在平面上，加前后景水泡形成视差，叠 3D 粒子/热气，相机缓慢推近。动的是镜头与环境，不是人物本身。
- 需要人物真正动起来的镜头（走路、转身、口型），仍用 `BlenderStudio` 的三维场景或既有动画链路，不用 FLUX 拼帧。

## 6. 验收

- `/system_stats` 可访问，模型列表含 FLUX.3。
- 单张生成 < 5 分钟；图像无明显文字伪影；人工确认构图与手部。
- 停止后 8188 不再监听。
