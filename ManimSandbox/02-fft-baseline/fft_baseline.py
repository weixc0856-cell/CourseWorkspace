import numpy as np

from manim import *


class FFTBaseline(Scene):
    """Technical baseline: decompose a waveform into two sinusoids."""

    def construct(self):
        title = Text("FFT baseline: two frequencies", font="DejaVu Sans", font_size=34)
        title.to_edge(UP)
        self.play(FadeIn(title))

        axes = Axes(
            x_range=[0, 2 * PI, PI / 2],
            y_range=[-1.2, 1.2, 0.5],
            x_length=10,
            y_length=3.2,
            tips=False,
            axis_config={"color": GREY_B},
        ).shift(DOWN * 0.8)
        labels = axes.get_axis_labels(x_label="t", y_label="f(t)")

        high = axes.plot(lambda x: 0.35 * np.sin(5 * x), color=TEAL, stroke_width=3)
        low = axes.plot(lambda x: 0.65 * np.sin(2 * x), color=ORANGE, stroke_width=3)
        total = axes.plot(
            lambda x: 0.65 * np.sin(2 * x) + 0.35 * np.sin(5 * x),
            color=YELLOW,
            stroke_width=4,
        )

        self.play(Create(axes), FadeIn(labels), run_time=1.2)
        self.play(Create(low), run_time=1.2)
        self.play(Create(high), run_time=1.2)
        self.play(Create(total), run_time=1.2)

        legend = VGroup(
            Text("low frequency", color=ORANGE, font="DejaVu Sans", font_size=24),
            Text("high frequency", color=TEAL, font="DejaVu Sans", font_size=24),
            Text("sum", color=YELLOW, font="DejaVu Sans", font_size=24),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        legend.to_corner(DR)
        self.play(FadeIn(legend))
        self.wait(1.0)
