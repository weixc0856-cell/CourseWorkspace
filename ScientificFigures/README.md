# ScientificFigures


> **2026-11-13 状态**：`check.ps1` = `check ok`。V2 的动画预览、声音资产、镜头表、锁定、M1 闭环修补，以及项目/运行契约、阶段 DAG、质量缺陷闭环与知识概念层均已落地；执行台账见 `docs/v2/m0/EXECUTION_PLAN.md`。`build/` 为临时区、`deliver/` 为最终交付区。
Scientific-figure POC for CourseWorkspace: SymPy → LaTeX, Matplotlib + SciencePlots → SVG/PDF/PNG.

- **Not** a video renderer and **not** a second course pipeline.
- Formulas still use the FormulaSpec/KaTeX pipeline; figures are static assets consumed by Remotion.
- Plotly/Seaborn are deferred (interactive/statistical, not needed for the first integration).

```powershell
uv sync --project ScientificFigures
uv run --project ScientificFigures python ScientificFigures/figures/continuity_figure.py
```
