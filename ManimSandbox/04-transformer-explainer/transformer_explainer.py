import numpy as np

from manim import *

TOKENS = ["The", "cat", "sat", "on", "the", "mat"]
WEIGHTS = np.array([0.12, 0.40, 0.18, 0.08, 0.07, 0.15])
SCORES = np.array([1.2, 4.0, 1.8, 0.8, 0.7, 1.5])


def token_row(tokens=TOKENS, y=3.0, scale=1.0):
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


def vector_column(values, color=TEAL, cell=0.24, opacity_base=0.25):
    column = VGroup()
    for value in values:
        square = Square(side_length=cell, stroke_width=1, stroke_color=GREY_D)
        square.set_fill(color, opacity=min(0.95, opacity_base + 0.6 * float(value)))
        column.add(square)
    column.arrange(DOWN, buff=0.03)
    return column


class TokensScene(Scene):
    """Shot 1: token ids become embeddings."""

    def construct(self):
        title = Text(
            "1. Token ids become embeddings", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))
        boxes = token_row(y=2.0)
        self.play(LaggedStart(*[FadeIn(box) for box in boxes], lag_ratio=0.08))

        ids = [3, 17, 42, 8, 3, 61]
        id_labels = VGroup()
        for index, (box, token_id) in enumerate(zip(boxes, ids)):
            label = Text(
                f"id {token_id}", font="DejaVu Sans", font_size=16, color=GREY_A
            ).next_to(box, UP, buff=0.1)
            id_labels.add(label)
        self.play(FadeIn(id_labels))

        rng = np.random.default_rng(7)
        vectors = VGroup()
        arrows = VGroup()
        for index, box in enumerate(boxes):
            values = rng.random(4)
            column = vector_column(values).next_to(box, DOWN, buff=0.28)
            arrow = Arrow(
                box.get_bottom(), column.get_top(), buff=0.05, stroke_width=2, color=GREY_B
            )
            vectors.add(column)
            arrows.add(arrow)
        self.play(LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.06))
        self.play(LaggedStart(*[FadeIn(vector) for vector in vectors], lag_ratio=0.06))

        note = Text(
            "token id -> learned embedding vector",
            font="DejaVu Sans",
            font_size=24,
            color=GREY_A,
        ).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(note))
        self.wait(1.0)


class QKVScene(Scene):
    """Shot 2: the same embedding is projected into Q, K and V."""

    def construct(self):
        title = Text(
            "2. Q, K and V are three projections", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))
        boxes = token_row(y=2.4, scale=0.9)
        self.play(FadeIn(boxes))

        rng = np.random.default_rng(11)
        k_values = [rng.random(4) for _ in TOKENS]
        v_values = [rng.random(4) for _ in TOKENS]

        q_label = Text("q", font="DejaVu Sans", font_size=26, color=YELLOW)
        q_column = vector_column(rng.random(4), color=YELLOW, cell=0.3)
        q_column.move_to([boxes[1].get_x(), 1.0, 0])
        q_label.next_to(q_column, UP, buff=0.1)
        self.play(FadeIn(q_label), FadeIn(q_column))

        k_columns = VGroup()
        v_columns = VGroup()
        for index, box in enumerate(boxes):
            k_column = vector_column(k_values[index], color=TEAL, cell=0.22)
            k_column.move_to([box.get_x(), -0.5, 0])
            v_column = vector_column(v_values[index], color=ORANGE, cell=0.22)
            v_column.move_to([box.get_x(), -1.9, 0])
            k_columns.add(k_column)
            v_columns.add(v_column)
        self.play(LaggedStart(*[FadeIn(column) for column in k_columns], lag_ratio=0.05))
        self.play(LaggedStart(*[FadeIn(column) for column in v_columns], lag_ratio=0.05))

        k_label = Text("k", font="DejaVu Sans", font_size=26, color=TEAL).next_to(
            k_columns, LEFT, buff=0.35
        )
        v_label = Text("v", font="DejaVu Sans", font_size=26, color=ORANGE).next_to(
            v_columns, LEFT, buff=0.35
        )
        formula = Text(
            "Q = X·W_Q    K = X·W_K    V = X·W_V",
            font="DejaVu Sans",
            font_size=26,
            color=GREY_B,
        ).next_to(v_columns, DOWN, buff=0.35)
        self.play(FadeIn(k_label), FadeIn(v_label), FadeIn(formula))
        self.wait(1.0)


class AttentionScene(Scene):
    """Shot 3: scores, scaling, softmax weights."""

    def construct(self):
        title = Text(
            "3. Scores become softmax weights", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))
        boxes = token_row(y=2.4, scale=0.9)
        self.play(FadeIn(boxes))

        q_column = vector_column([0.8, 0.4, 0.9, 0.3], color=YELLOW, cell=0.24)
        q_column.move_to([boxes[0].get_x() - 1.1, 1.0, 0])
        q_label = Text("q", font="DejaVu Sans", font_size=24, color=YELLOW).next_to(
            q_column, UP, buff=0.08
        )
        self.play(FadeIn(q_column), FadeIn(q_label))

        k_columns = VGroup()
        score_labels = VGroup()
        for index, box in enumerate(boxes):
            column = vector_column(
                [0.2 + 0.1 * index, 0.5, 0.3, 0.6], color=TEAL, cell=0.2
            )
            column.move_to([box.get_x(), 1.0, 0])
            k_columns.add(column)
            score = Text(
                f"{SCORES[index]:.1f}",
                font="DejaVu Sans",
                font_size=18,
                color=TEAL,
            ).next_to(column, DOWN, buff=0.12)
            score_labels.add(score)
        self.play(LaggedStart(*[FadeIn(column) for column in k_columns], lag_ratio=0.05))
        self.play(FadeIn(score_labels))

        bars = VGroup()
        weight_labels = VGroup()
        for index, weight in enumerate(WEIGHTS):
            bar = Rectangle(
                width=0.4,
                height=0.1 + 2.4 * float(weight),
                stroke_width=0,
                fill_color=YELLOW,
                fill_opacity=0.85,
            )
            bar.move_to([boxes[index].get_x(), -1.0 + bar.height / 2, 0])
            bars.add(bar)
            weight_labels.add(
                Text(
                    f"α={weight:.2f}",
                    font="DejaVu Sans",
                    font_size=16,
                    color=YELLOW,
                ).next_to(bar, RIGHT, buff=0.06)
            )
        self.play(
            LaggedStart(*[GrowFromEdge(bar, DOWN) for bar in bars], lag_ratio=0.08),
            run_time=1.4,
        )
        self.play(FadeIn(weight_labels))

        formula = Text(
            "score = q·k / √d_k      α = softmax(score)",
            font="DejaVu Sans",
            font_size=24,
            color=GREY_B,
        ).next_to(bars, DOWN, buff=0.35)
        self.play(FadeIn(formula))
        self.wait(1.0)


class OutputScene(Scene):
    """Shot 4: weighted values are summed into the context vector."""

    def construct(self):
        title = Text(
            "4. Weighted values sum into context", font="DejaVu Sans", font_size=36
        ).to_edge(UP)
        self.play(FadeIn(title))

        colors = [BLUE_B, TEAL, ORANGE, PURPLE, GREEN, RED]
        value_columns = VGroup()
        weight_labels = VGroup()
        for index, (weight, color) in enumerate(zip(WEIGHTS, colors)):
            column = vector_column(
                [weight, weight * 0.7, weight * 0.4], color=color, cell=0.3
            )
            column.move_to([-4.4 + index * 0.95, 0.6, 0])
            value_columns.add(column)
            weight_labels.add(
                Text(
                    f"α={weight:.2f}",
                    font="DejaVu Sans",
                    font_size=16,
                    color=color,
                ).next_to(column, DOWN, buff=0.12)
            )
        self.play(LaggedStart(*[FadeIn(column) for column in value_columns], lag_ratio=0.08))
        self.play(FadeIn(weight_labels))

        context = vector_column([1.0, 0.8, 0.55], color=YELLOW, cell=0.42)
        context.move_to([3.4, 0.7, 0])
        context_label = Text(
            "context(cat)", font="DejaVu Sans", font_size=24, color=YELLOW
        ).next_to(context, RIGHT, buff=0.3)
        arrows = VGroup()
        for column in value_columns:
            arrows.add(
                Arrow(
                    column.get_right(),
                    context.get_left(),
                    buff=0.08,
                    stroke_width=2,
                    color=GREY_B,
                    max_tip_length_to_length_ratio=0.1,
                )
            )
        self.play(LaggedStart(*[GrowArrow(arrow) for arrow in arrows], lag_ratio=0.06))
        self.play(FadeIn(context, scale=1.2), FadeIn(context_label))

        formula = Text(
            "context = Σ α_i · v_i",
            font="DejaVu Sans",
            font_size=28,
            color=YELLOW,
        ).to_edge(DOWN, buff=0.45)
        self.play(FadeIn(formula))
        self.wait(1.2)
