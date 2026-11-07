import numpy as np

from manim import *


class AttentionBaseline(Scene):
    """Product baseline: token weights and an attention heatmap."""

    def construct(self):
        title = Text(
            "Attention: query-key weights", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))

        tokens = ["The", "cat", "sat", "on", "the", "mat"]
        boxes = VGroup()
        for token in tokens:
            label = Text(token, font="DejaVu Sans", font_size=24)
            box = RoundedRectangle(
                corner_radius=0.12,
                width=max(1.0, label.width + 0.35),
                height=0.62,
                stroke_color=GREY_B,
                stroke_width=2,
            ).set_fill(BLACK, opacity=0.6)
            boxes.add(VGroup(box, label))
        boxes.arrange(RIGHT, buff=0.24).shift(UP * 2.35)
        self.play(LaggedStart(*[FadeIn(box, shift=UP * 0.2) for box in boxes], lag_ratio=0.08))

        weights = np.array([0.12, 0.40, 0.18, 0.08, 0.07, 0.15])
        bars = VGroup()
        labels = VGroup()
        for index, weight in enumerate(weights):
            bar = Rectangle(
                width=0.46,
                height=0.1 + 3.2 * float(weight),
                stroke_width=0,
                fill_color=YELLOW,
                fill_opacity=0.85,
            )
            bar.move_to([boxes[index].get_x(), -0.2 + bar.height / 2, 0])
            bars.add(bar)
            value = Text(
                f"{weight:.2f}", font="DejaVu Sans", font_size=20, color=YELLOW
            ).next_to(bar, UP, buff=0.08)
            labels.add(value)

        query = boxes[1]
        self.play(query[0].animate.set_stroke(YELLOW, width=4))
        self.play(
            LaggedStart(*[GrowFromEdge(bar, DOWN) for bar in bars], lag_ratio=0.08),
            run_time=1.6,
        )
        self.play(FadeIn(labels, shift=UP * 0.08), run_time=0.7)

        grid = VGroup()
        for row in range(len(tokens)):
            for col in range(len(tokens)):
                value = weights[col] if row == 1 else 0.05
                cell = Square(side_length=0.46, stroke_width=1, stroke_color=GREY_D)
                cell.set_fill(BLUE, opacity=min(0.95, 0.15 + float(value)))
                cell.move_to([-1.1 + col * 0.46, -1.15 - row * 0.46, 0])
                grid.add(cell)
        heatmap_label = Text(
            "attention heatmap", font="DejaVu Sans", font_size=22, color=GREY_A
        ).next_to(grid, LEFT, buff=0.4)

        self.play(FadeIn(grid), FadeIn(heatmap_label), run_time=1.2)
        note = Text(
            "softmax over keys", font="DejaVu Sans", font_size=24, color=GREY_A
        ).to_corner(DR, buff=0.3)
        self.play(FadeIn(note))
        self.wait(1.2)
