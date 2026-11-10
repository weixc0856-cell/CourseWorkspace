# Reveal.js 技术课件工程


> **2026-11-10 状态**：V1 收敛完成；`check.ps1` exit 0，六套 640 用例（634 通过、6 跳过）。C-16 片头 DEFERRED，不阻塞 V1。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
一个以 **纸白/橙色 Light Technical Editorial** 为视觉基调的双语技术课件环境。项目只包含一个 `reveal.js` 渲染外壳，具体课件内容全部放在**工作区根目录**的 `lessons/` 下，通过 URL 参数切换。生成课件前，请先阅读 [课件生成调用指南](docs/课件生成调用指南.md)。

## 快速开始

```bash
npm install
npm run dev
```

打开 `http://localhost:8081/?lesson=01-transformer-demo`。

不传 `lesson` 参数时，默认加载 `01-transformer-demo`。服务器只监听本地 `8081` 端口，`8080` 固定留给本地模型服务，依赖安装在本项目的 `node_modules/` 中，不使用全局安装。

> **端口约定**：本机本地模型服务（`<AI_ROOT>\start_server.bat`，OpenAI 兼容接口）固定占用 `8080`；课件预览默认使用 `8081`，两者可以同时运行。若 `8081` 已被占用，`live-server` 会自动顺延到下一个可用端口；需要固定端口时用 `npx live-server .. --port=<port> --entry-file=index.html --watch=lessons,CourseSlides/template,CourseSlides/css`。

## 目录结构

```text
.
├── css/
│   └── mckinsey-orange.css       # 麦肯锡橙白主题
├── docs/
│   └── 课件生成调用指南.md         # 生成器调用、交付与验收规范
├── template/
│   └── index.html                # 全局唯一的 reveal.js 渲染外壳
├── package.json
└── package-lock.json

../lessons/<lesson-slug>/          # 课程内容在工作区根目录，不在本工程内
├── slides.md                      # 双语示例课件（纯展示，无口播）
├── lecture_notes.md               # 讲师手册：逐字稿、时长、动画切入
├── lesson.yaml / storyboard.yaml  # 课程元数据与镜头清单
└── assets/                        # SVG / 图片资源
```

`live-server` 以工作区根目录为服务根，因此页面地址是 `/CourseSlides/template/?lesson=<slug>`；根目录的 `index.html` 会把 `/?lesson=<slug>` 转发到这里。

## 新建一套课件

1. 在工作区根目录新建 `lessons/<lesson-slug>/`，放入 `slides.md`（纯展示）、`lecture_notes.md`（逐字稿）与 `lesson.yaml`、`storyboard.yaml`，`assets/` 按需。
2. 用短横线小写命名 slug，例如 `02-attention-patterns`。
3. 访问 `http://localhost:8081/?lesson=02-attention-patterns`。
4. 在仓库 `docs/交付清单-<slug>.md` 建一份交付清单，模板见 [课程交付清单模板](../docs/课程交付清单模板.md)。

`slides.md` 只放观众能看到的内容：页标题、英文论点、公式/图表、`.zh-sub` 中文对照。口播、时长、导播提示、动画切入一律写进 `lecture_notes.md`，两边按 `Slide N` 一一对应。

外壳会自动拼接 Markdown 路径，不需要修改 `template/index.html`。

## 自动截图与构建

构建时由 `CourseControl` 的 `capture_slides` 阶段调用 Playwright 打开本工程，逐页截图：

```powershell
.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era
```

- 视口固定 1920×1080。
- 等待 `Reveal.isReady()`、字体和图片加载完成。
- 截图前隐藏 controls、progress、slide-number。
- 输出 `build/<slug>/slides/slide-###.png` 与 `capture-manifest.json`。
- 页数不一致或空图会失败，不会生成通过报告。
- `compose.mode=recording` 时不执行截图，改用录屏作为底稿。

截图实现见 [RemotionStudio/scripts/capture-slides.mjs](../RemotionStudio/scripts/capture-slides.mjs)。

### 图片路径

Markdown 是在浏览器里异步加载进外壳的，因此图片请使用以服务器根目录开头的路径：

```markdown
![diagram](/lessons/01-transformer-demo/assets/attention-flow.svg)
```

不要写成 `assets/attention-flow.svg`，它会相对 `template/` 或站点根目录解析，而不是相对 `slides.md`。

## Markdown 约定

- `---`：下一页（水平）
- `--`：当前页内的下半页（垂直）
- 不写 `Note:` / `Notes:`：本工程的口播稿独立存放在 `lecture_notes.md`，屏幕上不出现任何备注
- `<!-- .slide: data-background="#FFFFFF" -->`：给单页设置属性
- 每页的中文对照放在 `.zh-sub` 容器中，例如：

```html
<div class="zh-sub">
  <p>这里放中文对照。字号、颜色和虚线分隔由主题统一控制。</p>
</div>
```

## 配套动画

动态机制不进幻灯片。结构类演示（流程、序列、架构）由 [../MotionStudio](../MotionStudio) 用 Motion Canvas 生成，数学类演示（投影、曲率、坐标变换）由 [../ManimSandbox](../ManimSandbox) 生成，真实 3D 场景由 [../BlenderStudio](../BlenderStudio) 生成；三者都输出独立视频文件，最终由 [../RemotionStudio](../RemotionStudio) 按 `shots.json` 合成或交给剪辑软件处理。`slides.md` 里不写 `<video>`，也不做自动播放与尺寸适配。

这样安排是因为浏览器对自动播放策略、视频编码和画布缩放的处理并不一致，实机演示容易出意外；而独立 MP4 可以进合成或剪辑流程做画中画、局部缩放与变速。生成与构建流程见 [课件制作总指导](../docs/课件制作总指导.md)。

## 主题

主题变量集中在 [css/mckinsey-orange.css](css/mckinsey-orange.css) 顶部的 `:root`：

```css
--mk-white: #FFFFFF;
--mk-text: #1A1A1A;
--mk-text-muted: #595959;
--mk-orange: #EB6100;
--mk-orange-soft: #FFF5F0;
--mk-border: #E5E5E5;
```

已有样式包括 `h2` 的 2px 橙色下划线、左侧 4px 橙线的引用块、双栏布局 `.split`、指标卡 `.metric-grid`、内容卡 `.cards` / `.card`、公式块 `.equation`、流程条 `.sequence` 等，可直接在 Markdown 的 HTML 片段里使用。

## 依赖

- `reveal.js`：本地依赖
- `live-server`：本地开发依赖
- 开发命令：`live-server --port=8081 --entry-file=template/index.html --watch=lessons,template,css`

页面不依赖 CDN 字体或外部脚本，离线环境也能正常打开。
