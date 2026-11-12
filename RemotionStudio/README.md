# RemotionStudio


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个知识板块（本机开发，不入库）；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
最终视频编排工程。读取 `build/<lesson>/shots.json` 或 `build/<lesson>/contracts/timeline.spec.json`，把幻灯片画面、Blender / Motion Canvas / Manim / CodeVideo 成片、旁白和字幕组合成课程视频。

## 边界

- 读取：`shots.json` 或 `timeline.spec.json` 指向的素材、`lessons/<slug>/subtitles.srt`（可选）、`shared/design-tokens/tokens.json`。
- 写入：`build/<lesson>/final/`（渲染临时）、`build/<lesson>/remotion/`（临时）、本工程 `public/staging/`（渲染器要求的临时镜像）。最终交付由 CourseControl `package` 复制到 `deliver/<slug>/`。
- 不读取 `MotionStudio/`、`ManimSandbox/`、`BlenderStudio/` 的源码或产物目录；一切素材先进入 `build/`。
- 不做 TTS、不做语音识别、不做云端渲染。

## 环境

- Node.js `v24.14.1`，npm `11.11.0`
- Remotion `4.0.539`（`remotion` 与 `@remotion/cli` 同版本锁定）
- React `18.3.1`
- Playwright `1.64.1`，使用本机 Chrome（`channel: chrome`），不下载额外浏览器
- Studio 默认端口 `3000`

## 命令

```powershell
cd RemotionStudio

# 编辑器
npm run studio

# 截图：需要 8081 预览服务在运行
node scripts/capture-slides.mjs --lesson <slug>

# 只截前两页（冒烟）
node scripts/capture-slides.mjs --lesson <slug> --max 2

# 按 shots.json 复制素材到 public/staging/<lesson>/
node scripts/stage-assets.mjs --lesson <slug>

# 渲染 legacy shots.json
npx remotion render src/index.ts CourseVideo `
  ../build/<slug>/final/preview-remotion.mp4 `
  --props=../build/<slug>/shots.json

# 章节卡（探针入口，非生产；不进入课程构建）
npx remotion render src/probes/index.ts ChapterCard ../build/<lesson>/final/chapter-01.mp4 `
  --props=../build/<lesson>/contracts/chapter-01.json

# 渲染 V1 时间线（含 Ken Burns / TimelineSpec）
npx remotion render src/index.ts CourseTimeline `
  ../build/<slug>/final/preview-timeline.mp4 `
  --props=../build/<slug>/contracts/timeline.spec.json
```

## 素材访问（S-R3-1 结论）

**必须使用 staging。** Remotion 会把绝对路径规范化为 `file://`，Chromium 拒绝从页面加载本地文件；`file://` 直接传入同样失败。实测与结论见 [DECISIONS.md](../docs/DECISIONS.md) D-005。

规则：

1. `shots.json` 中的 `source` 始终相对 `build/<lesson>/`。
2. `stage-assets.mjs` 按 `source` 复制到 `public/staging/<lesson>/`，保持相对路径不变。
3. 组件通过 `staticFile('staging/<lesson>/<source>')` 引用。
4. `public/staging/` 是临时镜像，不作为事实源；成功构建后由 CourseControl 清理。旧的 staging 缓存已归入 `build/_engine-cache/remotion-staging/`。

## 时间线

`shots.json` 的片段分两类：

- `timeline_role: base`：顺序拼接，决定成片总长。`kind: slide` 用静态图，`kind: recording` 用录屏。
- `timeline_role: overlay`：叠在父片段内，不改变总长；`presentation` 决定呈现方式：
  - `cutaway`：全屏替换底稿；
  - `picture_in_picture`：右下角小窗，橙色描边；
  - `transparent_overlay`：全屏透明叠加。

转场为 0.3 秒淡入淡出，只作用于 overlay。

### 静帧运镜（Ken Burns）

- 时间线 `video[].metadata.legacy_motion` 由 `collect`/`v1_timeline` 写入；
- `src/components/MotionImage.tsx` 只对图片资产应用平移/缩放，视频不受影响；
- 参数来自 `lesson.yaml.motion`：`slides: ken_burns|static`、`scale`、`pan_percent`；
- `PrimerPoc` 是 30 秒模拟样片探针，位于 `src/probes/`，不进入生产入口。
- `ChapterCard` 与 `BrandPreview` 已移至 `src/probes/`；生产入口 `src/index.ts` 只注册课程与品牌片段。

## 旁白与字幕

- 旁白：`shots.json` 的 `narration.path` 相对 `build/<lesson>/`，staging 后由 `src/audio/Narration.tsx` 播放。
- 字幕：`shots.json` 的 `subtitles.path` 指向 `build/<lesson>/subtitles.srt`，staging 后由 `src/subtitles/Captions.tsx` 解析。
- 两者都由 `lesson.yaml` 的开关控制；关闭时不加载。
- 配音生成在 `<AI_ROOT>\VoxCPM-Runtime`，接入流程见 [本地模型与配音工作流](../docs/本地模型与配音工作流.md)。

## 结构

```text
src/
├── index.ts                 # registerRoot
├── Root.tsx                 # CourseVideo / AccessProbe composition
├── types.ts                 # shots.json 类型
├── compositions/
│   ├── CourseVideo.tsx      # 时间线与呈现
│   └── AccessProbe.tsx      # S-R3-1 素材访问探针
├── subtitles/Captions.tsx   # SRT 解析与渲染
├── audio/Narration.tsx      # 旁白音频
├── styles/tokens.ts         # 读取 shared/design-tokens
└── utils/timing.ts          # 秒/帧换算、SRT 解析
scripts/
├── capture-slides.mjs       # Playwright 逐页截图 + manifest
└── stage-assets.mjs         # build → public/staging
```

## 备注

- 中间帧使用 PNG（`Config.setVideoImageFormat('png')`），否则 H.264 输出为 `yuvj420p`；PRD 要求 `yuv420p`。
- 截图默认隐藏 Reveal 的 controls、progress、slide-number，保证画面干净。
- 截图 manifest 记录页码、文件、分辨率、字节数和来源；页数不一致视为失败。
- `AccessProbe` 仅用于验证素材访问，不参与课程成片。
