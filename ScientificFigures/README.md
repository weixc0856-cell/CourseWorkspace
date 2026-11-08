# ScientificFigures

Scientific-figure POC for CourseWorkspace: SymPy → LaTeX, Matplotlib + SciencePlots → SVG/PDF/PNG.

- **Not** a video renderer and **not** a second course pipeline.
- Formulas still use the FormulaSpec/KaTeX pipeline; figures are static assets consumed by Remotion.
- Plotly/Seaborn are deferred (interactive/statistical, not needed for the first integration).

```powershell
uv sync --project ScientificFigures
uv run --project ScientificFigures python ScientificFigures/figures/continuity_figure.py
```
