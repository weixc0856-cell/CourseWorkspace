"""Formula smoke: KaTeX-compatible LaTeX also renders through Manim MathTex."""
from __future__ import annotations

from manim import (
    DOWN,
    UP,
    FadeIn,
    MathTex,
    Scene,
    Text,
    VGroup,
    config,
)

config.background_color = "#FFFFFF"


class FormulaSmoke(Scene):
    def construct(self) -> None:
        title = Text("Formula pipeline · Manim", font="Arial", font_size=44, color="#14213D")
        title.to_edge(UP, buff=0.6)
        self.play(FadeIn(title), run_time=0.5)

        drag = MathTex(
            r"C_{\mathrm D}=\frac{F_{\mathrm D}}{\frac{1}{2}\rho U_\infty^2 A}",
            font_size=72,
            color="#14213D",
        )
        percent = MathTex(r"\frac{P}{P_0}=80\%", font_size=64, color="#0077B6")
        greek = MathTex(r"\rho,\ \mu,\ \alpha,\ \beta,\ \omega", font_size=56, color="#E76F51")
        group = VGroup(drag, percent, greek).arrange(DOWN, buff=0.65).shift(DOWN * 0.2)
        self.play(FadeIn(drag), run_time=0.8)
        self.play(FadeIn(percent), run_time=0.6)
        self.play(FadeIn(greek), run_time=0.6)
        self.wait(3.0)
