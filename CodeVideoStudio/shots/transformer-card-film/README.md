# transformer-card-film

三分钟 Transformer 科普片，24 张卡片，深浅交替，硬切。数据驱动：改 `cards.json` 就能改片子，不用碰绘制代码。

```powershell
# 预览
node CodeVideoStudio/skills/code-video/scripts/capture.mjs CodeVideoStudio/shots/transformer-card-film `
  --fps 30 --dur 180 --size 1920x1080 --selector canvas --chunk-seconds 60 --out build/transformer-3min.mp4
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `cards.json` | 24 张卡：时间、主题、类型、文案与图形参数 |
| `film.js` | 渲染器：`figure` / `statement` / `rule` / `bars` / `flow` 五种卡型 |
| `index.html` | 字体加载 → `document.fonts.ready` → 注入 `film.js` |
| `fonts/` | Jost 200/300（OFL-1.1），与 `RemotionStudio/public/fonts` 同一份字 |
| `SPEC.md` | 格式、输入、must-have |

## 约定

- **卡片边界即切点**：每张卡在 `u=0` 就是成立构图，`u` 内只做 settle 和缓慢推近。
- **主题按卡片声明**：`dark` 用于命题与数字，`light` 用于机制与结构。色值取 `shared/design-tokens/themes.json` 的 `deep_space` / `editorial_science` 两套。
- **字体不许回落**：`index.html` 先加载 Jost 并等待 `document.fonts.ready`，再启动渲染；中文由 `@fontsource/noto-sans-sc/300.css` 提供（靠 junction 指向 `RemotionStudio/node_modules`）。
- `window.seek(t)` 是唯一输入，无定时器、无未播种随机。

## 加一张卡

在 `cards.json` 的 `cards` 里插一条，改后续 `t`（或整段重新计时），不用改 `film.js`：

```json
{ "t": 187.5, "dur": 7.5, "theme": "light", "kind": "statement",
  "kicker": "补充", "headline": "一句话。" }
```

## 已知未做

- 旁白、字幕、配乐都没有。TTS（VoxCPM2，50000）本次未启动。
- 没有接进 lesson 的 storyboard；目前作为独立镜头渲染。
