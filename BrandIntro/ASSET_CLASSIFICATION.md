# BrandIntro 资产分类（2026-11-10）

- 范围：`CodeVideoStudio/shots/brand-desktop/`、`CodeVideoStudio/shots/brand-intro/`
- 目的：区分源码、参考素材、生成物与大型媒体，决定哪些进入仓库
- 生产引用：两目录都**没有**被 `CourseControl`、`RemotionStudio` 或课程构建引用；只被 `BrandIntro/` 与 `docs/品牌片头-3D桌面戏-设计.md` 引用

## 1. brand-desktop

| 类别 | 文件 | 处置 |
| --- | --- | --- |
| 源码/契约 | `SPEC.md`、`GATE1.md`、`cues.json`、`index.html`、`main.js` | 提交 |
| 依赖 | `fonts/*.woff2` | 提交 |
| 生成物 | `out/*.mp4`、`out/*.png`、`out/*.jpg` | 本地保留，不提交 |
| 运行时副本 | `three.module.js` | 由 `vendor-sync` 生成，`.gitignore` 排除 |

## 2. brand-intro

| 类别 | 文件 | 处置 |
| --- | --- | --- |
| 源码/契约 | `SPEC.md`、`VERIFY.md`、`build_character.py`、`build_scene.py`、`film.html`、`film.js`、`scene.html`、`scene.js`、`index.html`、`main.js` | 提交 |
| 角色/场景资产 | `character.blend`、`character.json`、`scene.blend` | 提交（重新渲染所需的最小资产） |
| 依赖 | `fonts/*.woff2`、`vendor/three/addons/**/*.js` | 提交 |
| 生成物 | `out/**`、`brand-rise/frame-*.png`、`env-*.png`、`character-{front,back,side,45,preview}.png` | 本地保留，不提交 |
| 临时备份 | `character.blend1`、`scene.blend1`、`film.before-c16.js` | 不提交 |
| 运行时副本 | `three.module.js` | 由 `vendor-sync` 生成，`.gitignore` 排除 |

`character.json` 是 `character.blend` 的导出，但 three.js 片头直接读取它；没有它无法重新渲染，因此提交（2.4 MB）。

## 3. 重复与无效文件

- `character.blend1`、`scene.blend1`：Blender 自动备份，删除不影响源文件；本轮保留在本地，不提交。
- `out/` 下有大量命名试验（`t*.mp4`、`k-*.png`、`e*-*.png`）：历史试验，保留本地，不提交。
- `three.module.js` 五份副本已由上轮收敛为唯一 `CodeVideoStudio/vendor/three/three.module.js`；镜头副本是构建产物。

## 4. 提交拆分

1. `brand-desktop` 源码与 Gate 1 记录（不含 `out/`）。
2. `brand-intro` 源码、角色/场景资产、C-16 颜色与构图修正、Gate 3 复核记录（不含 `out/` 与预览帧）。

生成物不进入仓库，但渲染命令与 Gate 结论可复现。
