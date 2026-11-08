# Motion Studio

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
- 编辑器草稿默认落在 `output/`，已 gitignore；**用于课程构建的成片不要留在 `output/`**，见下一节

键盘：`Space` 播放/暂停，`End` 跳到末帧，方向键逐帧。

## 构建集成

CourseControl 的 `render:motion_canvas` 采用“人工导出 + 控制层校验”的基线：

1. 在编辑器里导出 `Video (FFmpeg)` 的 MP4。
2. 放到 `build/<lesson-slug>/animation/<scene-stem>.mp4`。
   - 例：`src/scenes/01-shell-for-ai-era/gui_vs_cli_paths.tsx` → `build/01-shell-for-ai-era/animation/gui_vs_cli_paths.mp4`
3. 确认场景已注册在 `src/project.ts`。
4. 运行 `.\scripts\build-lesson.ps1 -Lesson <slug>`。

控制层会校验文件存在、分辨率、帧率与时长。文件缺失时：

- `allow_manual_animation_export: true` → 阶段 `skipped`（`manual_export_required`），最终 `incomplete`；
- 为 `false` → `fail`。

不会用截图拼帧或伪造文件冒充导出结果。原因与升级路径见 [DECISIONS.md](../docs/DECISIONS.md) D-004。

## 目录结构

```text
MotionStudio/
├── src/
│   ├── project.ts                        # 注册场景，决定时间轴顺序
│   ├── motion-canvas.d.ts                # 类型引用，缺了 tsc 会报 Callback 未定义
│   ├── styles/
│   │   └── mckinsey.ts                   # 麦肯锡橙白令牌，与课件 CSS 变量一一对应
│   └── scenes/
│       └── 01-transformer-demo/          # 目录名 = 课件 lesson slug
│           └── attention-flow.tsx        # 一个文件一个场景
├── vite.config.ts                        # motionCanvas + ffmpeg 插件
├── tsconfig.json
└── package.json
```

新增场景：

1. 在 `src/scenes/<lesson-slug>/` 下建 `<scene>.tsx`，默认导出 `makeScene2D(...)`
2. 在 `src/project.ts` 里 import `./scenes/<slug>/<scene>?scene` 并加进 `scenes`
3. 颜色与字体一律从 `src/styles/mckinsey.ts` 取，不写死十六进制

## 约定

- 场景内文字只用英文；中文对照放幻灯片的 `.zh-sub`
- 背景用 `view.fill(MK.white)`，与幻灯片纯白一致
- 单个机制 5~15 秒；超过 20 秒先拆场景
- 不引入外部图片、远程字体；图标用 `Line` / `Rect` / `Txt` 拼
- `tsc --noEmit` 必须通过（`npm run build` 会先跑它）
