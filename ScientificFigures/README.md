# ScientificFigures


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个知识板块（本机开发，不入库）；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
Scientific-figure POC for CourseWorkspace: SymPy → LaTeX, Matplotlib + SciencePlots → SVG/PDF/PNG.

- **Not** a video renderer and **not** a second course pipeline.
- Formulas still use the FormulaSpec/KaTeX pipeline; figures are static assets consumed by Remotion.
- Plotly/Seaborn are deferred (interactive/statistical, not needed for the first integration).

```powershell
uv sync --project ScientificFigures
uv run --project ScientificFigures python ScientificFigures/figures/continuity_figure.py
```
