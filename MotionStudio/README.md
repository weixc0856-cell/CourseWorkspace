# Motion Studio


> **2026-11-13 状态**：`check.ps1` = `check ok`。V2 的动画预览、声音资产、镜头表、锁定、M1 闭环修补，以及项目/运行契约、阶段 DAG、质量缺陷闭环与知识概念层均已落地；执行台账见 `docs/v2/m0/EXECUTION_PLAN.md`。`build/` 为临时区、`deliver/` 为最终交付区。
**首选动画引擎。** 基于 Motion Canvas 3.17（TypeScript + Vite），负责课件里"盒子、箭头、序列、流程"这一类离散结构的动画。与 [../CourseSlides](../CourseSlides) 同属前端技术栈，配色令牌直接共用。

## 适用与不适用

| 用它 | 换 [../ManimSandbox](../ManimSandbox) |
| --- | --- |
| 架构图、数据流、Token 序列流动 | 向量内积/外积、投影、特征空间旋转 |
| 算子树展开、Transformer 流水线 | 边界层速度剖面、对数律曲线推导 |
| 资产负债表流向、因果网络 | 激波相图、复变函数映射、流线/涡量场 |
| 排版、卡片、时间轴编排 | 需要 LaTeX 公式与坐标轴连续变换 |

需要真实 3D 空间、材质与灯光时用 [../BlenderStudio](../BlenderStudio)。

一句话：**画盒子和流程用这里，画坐标系和曲率去 Manim，真实三维去 Blender。**

## 环境

- Node.js（本机 v24）与本地 `node_modules/`，不装全局包
- 依赖锁在 `package-lock.json`；Motion Canvas 三件套固定 3.17.2
- `vite` 固定在 4.x：`@motion-canvas/ffmpeg` 的 peer 只认 4.x，升到 5 会解析失败
- 无头导出复用 `../RemotionStudio/node_modules` 的 Playwright 与本机 Chrome；需先安装 RemotionStudio 依赖

首次：

```powershell
cd CourseWorkspace\MotionStudio
npm install
```

## 日常使用

```powershell
npm run serve
```

打开 `http://localhost:5173`，得到 Motion Canvas 编辑器：

- 中间是画布预览，下方是时间轴，可以拖播放头、拖节点、改属性并实时热重载
- 左上 **VIDEO SETTINGS** 里设置分辨率（默认 1920×1080）、帧率、渲染范围
- 右下 **RENDER** 导出：`Image sequence` 出 PNG 序列，装好 `@motion-canvas/ffmpeg` 后可选 `Video (FFmpeg)` 直接出 MP4/WebM
- 编辑器草稿默认落在 `output/`，已 gitignore；**用于课程构建的成片不要留在 `output/`**，见下一节。课程构建产物在 `build/<slug>/animation/`，最终交付在 `deliver/<slug>/`；旧的 `MotionStudio/output/` 已清理

键盘：`Space` 播放/暂停，`End` 跳到末帧，方向键逐帧。

## 无头导出

`scripts/render-headless.mjs` 用 Motion Canvas core `Renderer` 在无 UI 页面中渲染，不点击编辑器：

1. 启动 Vite（4173）和 Node 帧接收器（4174）；
2. Playwright/Chrome 打开 `headless.html`，`Renderer` 逐帧调用自定义 exporter；
3. 每帧 PNG POST 到接收器，ffmpeg 编码 MP4；
4. ffprobe 校验分辨率、帧率、帧数，并写 `build/motion-canvas/<run>/meta.json`。

```powershell
cd MotionStudio
node scripts/render-headless.mjs --scene attention-flow --fps 30 --width 1920 --height 1080 `
  --out ../build/motion-canvas/attention-flow.mp4
```

## 构建集成

CourseControl 的 `render:motion_canvas` 自动调用上面的脚本：

1. 场景放进 `src/scenes/<lesson>/<scene>.tsx` 就会被发现：`scripts/sync-scenes.mjs` 生成 `src/scenes.generated.js`，`render-headless.mjs` 在启动前自动跑一次；生成物不入库；
2. 输出固定为 `build/<lesson-slug>/animation/<scene-stem>.mp4`；
3. adapter 最多重试 2 次，ffprobe 通过后才 `pass`；
4. 仍失败 → `fail`，不写 `skipped` / `incomplete`；合法的旧人工导出可复用，但不是默认路径。

例：`<内容根>/engines/motion_canvas/scenes/<lesson>/<scene>.tsx` → `build/<slug>/animation/<scene>.mp4`。

不会用截图拼帧或伪造文件冒充导出结果。见 [DECISIONS.md](../docs/DECISIONS.md) D-054。

## 目录结构

```text
MotionStudio/
├── headless.html                        # 无头渲染页
├── src/
│   ├── headless.js                      # core Renderer + 自定义帧接收 exporter
│   ├── project.ts                        # 从 scenes.generated 注册场景，决定时间轴顺序
│   ├── scenes.generated.js               # 由 sync-scenes.mjs 生成，不入库
│   ├── motion-canvas.d.ts                # 类型引用，缺了 tsc 会报 Callback 未定义
│   ├── styles/
│   │   └── mckinsey.ts                   # 麦肯锡橙白令牌，与课件 CSS 变量一一对应
│   └── scenes/
│       ├── <lesson>/                     # 课程场景目录（指向内容根的 junction）
│       │   └── <scene>.tsx               # 一个文件一个场景
│       └── lesson-manual/                # 仓库夹具场景（adapter 测试用）
├── scripts/sync-scenes.mjs               # 扫描场景目录，生成场景注册表
├── scripts/render-headless.mjs           # Vite + Playwright + 帧接收器 + ffmpeg
├── vite.config.ts                        # motionCanvas + ffmpeg 插件
├── tsconfig.json
└── package.json
```

新增场景：

1. 在 `src/scenes/<lesson-slug>/` 下建 `<scene>.tsx`，默认导出 `makeScene2D(...)`
2. 在 `src/project.ts` 里 import `./scenes/<slug>/<scene>?scene` 并加进 `scenes`
3. 在 `src/headless.js` 的 `scenes` 映射里加入 kebab-case scene id（文件名下划线转连字符）
4. 颜色与字体一律从 `src/styles/mckinsey.ts` 取，不写死十六进制

## 约定

- 场景内文字只用英文；中文对照放幻灯片的 `.zh-sub`
- 背景用 `view.fill(MK.white)`，与幻灯片纯白一致
- 单个机制 5~15 秒；超过 20 秒先拆场景
- 不引入外部图片、远程字体；图标用 `Line` / `Rect` / `Txt` 拼
- `tsc --noEmit` 必须通过（`npm run build` 会先跑它）
