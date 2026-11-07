"""E6.5 Multi-Head Attention visual scene.

All numbers come from ``multi_head_math.py``; this file only lays them out.
"""

from __future__ import annotations

from manim import *

from multi_head_math import (
    QUERY_INDEX,
    TOKENS,
    W_K1,
    W_K2,
    W_O,
    W_Q1,
    W_Q2,
    W_V1,
    W_V2,
    X,
    compute,
)

HEAD1 = YELLOW
HEAD2 = TEAL
CONCAT = PURPLE_B
OUTPUT = ORANGE
VALUE_FONT = 15


def format_value(value: float) -> str:
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}"


def matrix_grid(
    values,
    *,
    row_labels=None,
    col_labels=None,
    cell=0.45,
    font_size=VALUE_FONT,
    color=WHITE,
) -> VGroup:
    rows = len(values)
    cols = len(values[0])
    cells = VGroup()
    for row in range(rows):
        for col in range(cols):
            square = Square(side_length=cell, stroke_width=1.2, stroke_color=GREY_D)
            square.set_fill(BLACK, opacity=0.45)
            label = Text(
                format_value(float(values[row][col])),
                font="Arial",
                font_size=font_size,
                color=color,
            )
            label.move_to(square)
            cell_group = VGroup(square, label).move_to([col * cell, -row * cell, 0])
            cells.add(cell_group)
    grid = VGroup(*cells)
    group = VGroup(grid)
    if row_labels:
        row_text = VGroup(
            *[
                Text(label, font="Arial", font_size=font_size + 2, color=GREY_A)
                .next_to(cells[row * cols], LEFT, buff=0.12)
                for row, label in enumerate(row_labels)
            ]
        )
        group.add(row_text)
    if col_labels:
        col_text = VGroup(
            *[
                Text(label, font="Arial", font_size=font_size, color=GREY_A)
                .next_to(cells[col], UP, buff=0.1)
                for col, label in enumerate(col_labels)
            ]
        )
        group.add(col_text)
    return group


def alpha_heatmap(
    values,
    *,
    row_labels=None,
    col_labels=None,
    cell=0.52,
    font_size=12,
    base_color=HEAD1,
) -> VGroup:
    rows = len(values)
    cols = len(values[0])
    cells = VGroup()
    for row in range(rows):
        for col in range(cols):
            value = float(values[row][col])
            square = Square(side_length=cell, stroke_width=1, stroke_color=GREY_D)
            square.set_fill(base_color, opacity=min(0.95, 0.08 + 1.1 * value))
            label = Text(
                f"{value:.2f}",
                font="Arial",
                font_size=font_size,
                color=WHITE,
            )
            label.move_to(square)
            cells.add(VGroup(square, label).move_to([col * cell, -row * cell, 0]))
    group = VGroup(VGroup(*cells))
    if row_labels:
        group.add(
            VGroup(
                *[
                    Text(label, font="Arial", font_size=font_size + 3, color=GREY_A)
                    .next_to(cells[row * cols], LEFT, buff=0.1)
                    for row, label in enumerate(row_labels)
                ]
            )
        )
    if col_labels:
        group.add(
            VGroup(
                *[
                    Text(label, font="Arial", font_size=font_size, color=GREY_A)
                    .next_to(cells[col], UP, buff=0.08)
                    for col, label in enumerate(col_labels)
                ]
            )
        )
    return group


def row_highlight(matrix: VGroup, row: int, cols: int, color=YELLOW) -> SurroundingRectangle:
    cells = matrix[0]
    row_cells = VGroup(*[cells[row * cols + col] for col in range(cols)])
    return SurroundingRectangle(row_cells, color=color, buff=0.035).set_stroke(width=3)


def labeled(name: str, grid: VGroup, color=WHITE) -> VGroup:
    return VGroup(
        Text(name, font="Arial", font_size=20, color=color).next_to(
            grid, DOWN, buff=0.18
        ),
        grid,
    )


def head_panel(name: str, color) -> VGroup:
    box = RoundedRectangle(
        corner_radius=0.12,
        width=3.7,
        height=1.35,
        stroke_color=color,
        stroke_width=2.5,
    ).set_fill(BLACK, opacity=0.35)
    label = Text(name, font="Arial", font_size=22, color=color).move_to(
        box.get_top() + DOWN * 0.38
    )
    detail = Text(
        "W_Q, W_K, W_V  →  Q, K, V",
        font="Arial",
        font_size=17,
        color=GREY_A,
    ).move_to(box.get_bottom() + UP * 0.38)
    return VGroup(box, label, detail)


class MultiHeadScene(Scene):
    def construct(self):
        self.camera.background_color = "#0b0f14"
        result = compute()
        head1 = result["heads"][0]
        head2 = result["heads"][1]
        self.beat1()
        self.beat2(head1)
        self.beat3(head1, head2)
        self.beat4(result)
        self.beat5(result)
        self.wait(1.5)

    def title(self, text: str) -> Text:
        title = Text(text, font="Arial", font_size=34, color=WHITE).to_edge(
            UP, buff=0.35
        )
        self.play(FadeIn(title))
        return title

    def formula(self, text: str, color=GREY_B) -> Text:
        formula = Text(text, font="Arial", font_size=22, color=color).to_edge(
            DOWN, buff=0.4
        )
        self.play(FadeIn(formula))
        return formula

    def clear_all(self):
        if self.mobjects:
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.35)
        self.clear()

    def beat1(self):
        self.next_section("B1")
        self.title("Multi-Head: one input, two heads")
        x_grid = matrix_grid(
            X,
            row_labels=TOKENS,
            col_labels=["d1", "d2", "d3", "d4"],
            cell=0.55,
            font_size=18,
        )
        x_grid.move_to([-3.9, 0.15, 0])
        x_label = Text("X: 4 tokens × 4 dims", font="Arial", font_size=20, color=GREY_A)
        x_label.next_to(x_grid, DOWN, buff=0.35)
        head1 = head_panel("Head 1", HEAD1).move_to([4.0, 1.15, 0])
        head2 = head_panel("Head 2", HEAD2).move_to([4.0, -1.15, 0])
        arrow1 = Arrow(
            x_grid.get_right(),
            head1.get_left(),
            buff=0.15,
            stroke_width=3,
            color=HEAD1,
        )
        arrow2 = Arrow(
            x_grid.get_right(),
            head2.get_left(),
            buff=0.15,
            stroke_width=3,
            color=HEAD2,
        )
        note = Text(
            "same X · independent weights",
            font="Arial",
            font_size=20,
            color=GREY_B,
        ).to_edge(DOWN, buff=0.45)
        self.play(FadeIn(x_grid), FadeIn(x_label), run_time=1.0)
        self.play(FadeIn(head1), FadeIn(head2), run_time=0.8)
        self.play(GrowArrow(arrow1), GrowArrow(arrow2), run_time=0.8)
        self.play(FadeIn(note))
        self.wait(1.6)

    def beat2(self, head1):
        self.next_section("B2")
        self.clear_all()
        self.title("Head 1: its own Q, K and V")
        w_group = VGroup(
            labeled("W_Q1", matrix_grid(W_Q1, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
            labeled("W_K1", matrix_grid(W_K1, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
            labeled("W_V1", matrix_grid(W_V1, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
        ).arrange(RIGHT, buff=1.0)
        w_group.move_to([0, 0.4, 0])
        self.play(LaggedStart(*[FadeIn(item) for item in w_group], lag_ratio=0.12), run_time=1.3)
        formula = self.formula("Q1 = X·W_Q1     K1 = X·W_K1     V1 = X·W_V1", HEAD1)
        self.wait(1.2)

        self.play(FadeOut(w_group), FadeOut(formula), run_time=0.35)
        qkv = VGroup(
            labeled("Q1", matrix_grid(head1["q"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
            labeled("K1", matrix_grid(head1["k"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
            labeled("V1", matrix_grid(head1["v"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD1), HEAD1),
        ).arrange(RIGHT, buff=0.9)
        qkv.move_to([0, 0.35, 0])
        highlights = VGroup(*[row_highlight(item[-1], QUERY_INDEX, 2, HEAD1) for item in qkv])
        self.play(LaggedStart(*[FadeIn(item) for item in qkv], lag_ratio=0.12), run_time=1.2)
        self.play(Create(highlights), run_time=0.6)
        self.wait(1.3)

        self.play(FadeOut(qkv), FadeOut(highlights), run_time=0.35)
        alpha = alpha_heatmap(
            head1["alpha"],
            row_labels=TOKENS,
            col_labels=TOKENS,
            base_color=HEAD1,
        )
        alpha.move_to([-3.2, 0.3, 0])
        context = matrix_grid(
            head1["context"],
            row_labels=TOKENS,
            col_labels=["c1", "c2"],
            color=HEAD1,
        )
        context.next_to(alpha, RIGHT, buff=1.1)
        context_label = Text("context1", font="Arial", font_size=20, color=HEAD1)
        context_label.next_to(context, DOWN, buff=0.2)
        focus = Text(
            "cat row: max α = 0.65 at The",
            font="Arial",
            font_size=18,
            color=HEAD1,
        ).next_to(alpha, DOWN, buff=0.4)
        self.play(FadeIn(alpha), FadeIn(context), FadeIn(context_label), run_time=1.2)
        self.play(FadeIn(focus))
        self.formula("α1 = softmax(Q1·K1ᵀ / √d_k)     context1 = α1·V1", HEAD1)
        self.wait(1.5)

    def beat3(self, head1, head2):
        self.next_section("B3")
        self.clear_all()
        self.title("Head 2: another projection, another focus")
        w_group = VGroup(
            labeled("W_Q2", matrix_grid(W_Q2, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
            labeled("W_K2", matrix_grid(W_K2, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
            labeled("W_V2", matrix_grid(W_V2, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
        ).arrange(RIGHT, buff=1.0)
        w_group.move_to([0, 0.4, 0])
        self.play(LaggedStart(*[FadeIn(item) for item in w_group], lag_ratio=0.12), run_time=1.3)
        formula = self.formula("Q2 = X·W_Q2     K2 = X·W_K2     V2 = X·W_V2", HEAD2)
        self.wait(1.2)

        self.play(FadeOut(w_group), FadeOut(formula), run_time=0.35)
        qkv = VGroup(
            labeled("Q2", matrix_grid(head2["q"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
            labeled("K2", matrix_grid(head2["k"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
            labeled("V2", matrix_grid(head2["v"], row_labels=TOKENS, col_labels=["k1", "k2"], color=HEAD2), HEAD2),
        ).arrange(RIGHT, buff=0.9)
        qkv.move_to([0, 0.35, 0])
        highlights = VGroup(*[row_highlight(item[-1], QUERY_INDEX, 2, HEAD2) for item in qkv])
        self.play(LaggedStart(*[FadeIn(item) for item in qkv], lag_ratio=0.12), run_time=1.2)
        self.play(Create(highlights), run_time=0.6)
        self.wait(1.2)

        self.play(FadeOut(qkv), FadeOut(highlights), run_time=0.35)
        alpha2 = alpha_heatmap(
            head2["alpha"],
            row_labels=TOKENS,
            col_labels=TOKENS,
            base_color=HEAD2,
        )
        alpha2.move_to([-3.2, 0.3, 0])
        context2 = matrix_grid(
            head2["context"],
            row_labels=TOKENS,
            col_labels=["c1", "c2"],
            color=HEAD2,
        )
        context2.next_to(alpha2, RIGHT, buff=1.1)
        context2_label = Text("context2", font="Arial", font_size=20, color=HEAD2)
        context2_label.next_to(context2, DOWN, buff=0.2)
        focus2 = Text(
            "cat row: max α = 0.65 at sat",
            font="Arial",
            font_size=18,
            color=HEAD2,
        ).next_to(alpha2, DOWN, buff=0.4)
        self.play(FadeIn(alpha2), FadeIn(context2), FadeIn(context2_label), run_time=1.2)
        self.play(FadeIn(focus2))
        self.formula("α2 = softmax(Q2·K2^T / √d_k)     context2 = α2·V2", HEAD2)
        compare = VGroup(
            Text("α1(cat):  The .65 · cat .04 · sat .16 · on .16", font="Arial", font_size=17, color=HEAD1),
            Text("α2(cat):  The .16 · cat .16 · sat .65 · on .04", font="Arial", font_size=17, color=HEAD2),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        compare.to_edge(DOWN, buff=1.1)
        self.play(FadeIn(compare), run_time=0.8)
        self.wait(2.0)

    def beat4(self, result):
        self.next_section("B4")
        self.clear_all()
        self.title("Concatenate the two heads")
        head1 = result["heads"][0]
        head2 = result["heads"][1]
        context1 = matrix_grid(
            head1["context"],
            row_labels=TOKENS,
            col_labels=["c1", "c2"],
            color=HEAD1,
        )
        context2 = matrix_grid(
            head2["context"],
            row_labels=TOKENS,
            col_labels=["c1", "c2"],
            color=HEAD2,
        )
        concat = matrix_grid(
            result["concat"],
            row_labels=TOKENS,
            col_labels=["c1", "c2", "c3", "c4"],
            color=CONCAT,
        )
        context1.move_to([-4.8, 0.2, 0])
        context2.move_to([-2.4, 0.2, 0])
        concat.move_to([2.4, 0.15, 0])
        labels = VGroup(
            Text("context1", font="Arial", font_size=18, color=HEAD1),
            Text("context2", font="Arial", font_size=18, color=HEAD2),
            Text("concat", font="Arial", font_size=18, color=CONCAT),
        )
        labels[0].next_to(context1, DOWN, buff=0.2)
        labels[1].next_to(context2, DOWN, buff=0.2)
        labels[2].next_to(concat, DOWN, buff=0.2)
        highlight = row_highlight(concat, QUERY_INDEX, 4, CONCAT)
        self.play(FadeIn(context1), FadeIn(context2), FadeIn(labels[0]), FadeIn(labels[1]), run_time=1.0)
        self.play(FadeIn(concat), FadeIn(labels[2]), run_time=0.8)
        self.play(Create(highlight), run_time=0.6)
        self.formula("concat = [ head1 | head2 ]     4 = 2 + 2", CONCAT)
        self.wait(2.0)

    def beat5(self, result):
        self.next_section("B5")
        self.clear_all()
        self.title("Output projection returns to d_model")
        w_o = matrix_grid(
            W_O,
            col_labels=["d1", "d2", "d3", "d4"],
            color=OUTPUT,
        )
        final = matrix_grid(
            result["final"],
            row_labels=TOKENS,
            col_labels=["d1", "d2", "d3", "d4"],
            color=OUTPUT,
        )
        w_o.move_to([-3.0, 0.3, 0])
        final.move_to([3.0, 0.3, 0])
        w_label = Text("W_O (4×4)", font="Arial", font_size=19, color=OUTPUT)
        f_label = Text("final (4×4)", font="Arial", font_size=19, color=OUTPUT)
        w_label.next_to(w_o, DOWN, buff=0.2)
        f_label.next_to(final, DOWN, buff=0.2)
        highlight = row_highlight(final, QUERY_INDEX, 4, OUTPUT)
        self.play(FadeIn(w_o), FadeIn(w_label), run_time=0.8)
        self.play(FadeIn(final), FadeIn(f_label), run_time=0.8)
        self.play(Create(highlight), run_time=0.5)
        self.formula("final = concat · W_O     (4×4)·(4×4) = 4×4", OUTPUT)
        dims = Text(
            "X 4×4  →  Q/K/V 4×2  →  concat 4×4  →  final 4×4",
            font="Arial",
            font_size=18,
            color=GREY_A,
        ).to_edge(DOWN, buff=1.05)
        self.play(FadeIn(dims))
        self.wait(2.2)
