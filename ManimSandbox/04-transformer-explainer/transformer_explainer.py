import numpy as np

from manim import *

TOKENS = ["The", "cat", "sat", "on", "the", "mat"]


def token_row(tokens=TOKENS, y=2.4, scale=1.0):
    boxes = VGroup()
    for token in tokens:
        label = Text(token, font="DejaVu Sans", font_size=24 * scale)
        box = RoundedRectangle(
            corner_radius=0.12,
            width=max(1.0, label.width + 0.35),
            height=0.62,
            stroke_color=GREY_B,
            stroke_width=2,
        ).set_fill(BLACK, opacity=0.6)
        boxes.add(VGroup(box, label))
    boxes.arrange(RIGHT, buff=0.24)
    boxes.move_to([0, y, 0])
    return boxes


def vector_column(values, color=TEAL, cell=0.28):
    column = VGroup()
    for value in values:
        square = Square(side_length=cell, stroke_width=1, stroke_color=GREY_D)
        square.set_fill(color, opacity=0.25 + 0.6 * float(value))
        column.add(square)
    column.arrange(DOWN, buff=0.04)
    return column


class TokensScene(Scene):
    """Shot 1: tokens become vectors."""

    def construct(self):
        title = Text(
            "1. Tokens become vectors", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))
        boxes = token_row(y=2.0)
        self.play(LaggedStart(*[FadeIn(box) for box in boxes], lag_ratio=0.08))

        vectors = VGroup()
        arrows = VGroup()
        rng = np.random.default_rng(7)
        for index, box in enumerate(boxes):
            values = rng.random(4)
            column = vector_column(values).next_to(box, DOWN, buff=0.28)
            arrow = Arrow(
                box.get_bottom(),
                column.get_top(),
                buff=0.05,
                stroke_width=2,
                color=GREY_B,
            )
            vectors.add(column)
            arrows.add(arrow)
        self.play(LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.06))
        self.play(LaggedStart(*[FadeIn(vector) for vector in vectors], lag_ratio=0.06))

        note = Text(
            "each token -> a learned vector", font="DejaVu Sans", font_size=24, color=GREY_A
        ).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(note))
        self.wait(1.0)


class AttentionScene(Scene):
    """Shot 2: query-key weights and softmax."""

    def construct(self):
        title = Text(
            "2. Each token asks: who matters?", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))
        boxes = token_row(y=2.2)
        self.play(FadeIn(boxes))

        weights = np.array([0.12, 0.40, 0.18, 0.08, 0.07, 0.15])
        bars = VGroup()
        labels = VGroup()
        for index, weight in enumerate(weights):
            bar = Rectangle(
                width=0.42,
                height=0.1 + 2.8 * float(weight),
                stroke_width=0,
                fill_color=YELLOW,
                fill_opacity=0.85,
            )
            bar.move_to([boxes[index].get_x(), -0.1 + bar.height / 2, 0])
            bars.add(bar)
            labels.add(
                Text(
                    f"{weight:.2f}", font="DejaVu Sans", font_size=18, color=YELLOW
                ).next_to(bar, UP, buff=0.06)
            )

        query = boxes[1]
        self.play(query[0].animate.set_stroke(YELLOW, width=4))
        self.play(
            LaggedStart(*[GrowFromEdge(bar, DOWN) for bar in bars], lag_ratio=0.08),
            run_time=1.4,
        )
        self.play(FadeIn(labels))
        formula = Text(
            "softmax(q · k)", font="DejaVu Sans", font_size=28, color=YELLOW
        ).next_to(bars, DOWN, buff=0.5)
        self.play(FadeIn(formula))

        grid = VGroup()
        for row in range(len(TOKENS)):
            for col in range(len(TOKENS)):
                value = weights[col] if row == 1 else 0.05
                cell = Square(side_length=0.36, stroke_width=1, stroke_color=GREY_D)
                cell.set_fill(BLUE, opacity=min(0.95, 0.12 + float(value)))
                cell.move_to([3.9 + col * 0.4, -1.2 - row * 0.4, 0])
                grid.add(cell)
        heat_label = Text(
            "attention heatmap", font="DejaVu Sans", font_size=18, color=GREY_A
        ).next_to(grid, UP, buff=0.2)
        self.play(FadeIn(grid), FadeIn(heat_label), run_time=1.0)
        self.wait(1.0)


class OutputScene(Scene):
    """Shot 3: weighted sum becomes context."""

    def construct(self):
        title = Text(
            "3. Weighted sum becomes context", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))

        weights = [0.12, 0.40, 0.18, 0.08, 0.07, 0.15]
        colors = [BLUE_B, TEAL, ORANGE, PURPLE, GREEN, RED]
        vectors = VGroup()
        labels = VGroup()
        for index, (weight, color) in enumerate(zip(weights, colors)):
            column = vector_column(
                [weight, weight * 0.7, weight * 0.4], color=color, cell=0.34
            )
            column.move_to([-4.2 + index * 0.85, 0.4, 0])
            vectors.add(column)
            labels.add(
                Text(
                    f"{weight:.2f}", font="DejaVu Sans", font_size=18, color=color
                ).next_to(column, DOWN, buff=0.15)
            )
        self.play(LaggedStart(*[FadeIn(vector) for vector in vectors], lag_ratio=0.08))

        context = vector_column([1.0, 0.8, 0.55], color=YELLOW, cell=0.42)
        context.move_to([1.6, 0.5, 0])
        context_label = Text(
            "context(cat)", font="DejaVu Sans", font_size=24, color=YELLOW
        ).next_to(context, RIGHT, buff=0.3)
        arrows = VGroup()
        for vector in vectors:
            arrows.add(
                Arrow(
                    vector.get_right(),
                    context.get_left(),
                    buff=0.08,
                    stroke_width=2,
                    color=GREY_B,
                    max_tip_length_to_length_ratio=0.12,
                )
            )
        self.play(LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.06))
        self.play(FadeIn(context, scale=1.2), FadeIn(context_label))

        note = Text(
            "the context vector is passed to the next layer",
            font="DejaVu Sans",
            font_size=22,
            color=GREY_A,
        ).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(note))
        self.wait(1.2)
