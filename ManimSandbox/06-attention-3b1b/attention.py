"""Attention, explained visually. A 3Blue1Brown-style two-minute piece.

One mechanism: how a token's query is scored against every key, masked,
softmaxed, and used to mix value vectors into a context vector.

Picture and voice share one clock: shot boundaries come from
build/attention-3b1b/timing.json, written by gen_narration.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from manim import *

BG = "#000000"
CREAM = "#ECECEC"
MUTED = "#8C8C8C"
DIM = "#3A3F47"
BLUE = "#58C4DD"
RED = "#FC6255"
GREEN = "#83C167"
YELLOW = "#F4D345"
PURPLE = "#9A72AC"

TOKENS = ["the", "animal", "didn't", "cross", "the", "street", "because", "it", "was", "tired"]
IT = 7
ANIMAL = 1

config.background_color = BG

ROOT = Path(__file__).resolve().parents[2]
TIMING = ROOT / "build" / "attention-3b1b" / "timing.json"

DEFAULT_DURS = [10.5, 9.5, 10.5, 11.0, 12.0, 10.0, 11.0, 12.0, 9.0, 12.0, 10.5]


def serif(text: str, size: float = 30, color: str = CREAM, **kwargs):
    """Computer Modern serif, the voice of the reference style."""
    return MathTex(r"\text{" + text + "}", font_size=size, color=color, **kwargs)


def vec(start, end, color, width: float = 5.0, opacity: float = 1.0):
    return Arrow(
        start,
        end,
        buff=0,
        color=color,
        stroke_width=width,
        stroke_opacity=opacity,
        fill_opacity=opacity,
        max_tip_length_to_length_ratio=0.13,
        max_stroke_width_to_length_ratio=80,
    )


def load_bounds() -> list[float]:
    if TIMING.exists():
        data = json.loads(TIMING.read_text(encoding="utf-8"))
        segs = data["segments"]
        starts = [0.0] + [s["start"] for s in segs[1:]]
        return starts + [data["total"]]
    bounds, t = [0.0], 0.0
    for d in DEFAULT_DURS:
        t += d
        bounds.append(round(t, 3))
    return bounds


def score_matrix() -> np.ndarray:
    rng = np.random.default_rng(3)
    s = rng.normal(0.35, 0.75, (10, 10))
    s[IT] = [0.9, 3.4, 0.5, 1.15, 0.35, 2.55, 0.65, 1.05, 0.45, 0.25]
    return np.clip(s, -0.8, 3.6)


SCORES = score_matrix()
MASKED = SCORES[IT].copy()
MASKED[IT + 1 :] = -1e9
WEIGHTS = np.exp(MASKED - MASKED.max())
WEIGHTS = WEIGHTS / WEIGHTS.sum()


class AttentionScene(MovingCameraScene):
    def construct(self):
        self.bounds = load_bounds()
        self.words = VGroup()
        self.box = VMobject()
        self.qmark = VMobject()
        self.panel = []
        self.shots = [
            self.shot_sentence,
            self.shot_vector,
            self.shot_qkv,
            self.shot_roles,
            self.shot_dot,
            self.shot_alignments,
            self.shot_grid,
            self.shot_mask,
            self.shot_softmax,
            self.shot_mix,
            self.shot_answer,
        ]
        for i, shot in enumerate(self.shots):
            shot()
            self.sync_to(i + 1)

    # ---------- clock ----------
    def sync_to(self, index: int) -> None:
        target = self.bounds[index]
        now = self.renderer.time
        if target - now > 0.06:
            self.wait(target - now)
        elif now - target > 0.12:
            print(f"[timing] shot {index} overran by {now - target:.2f}s", flush=True)

    def reset_camera(self) -> None:
        self.camera.frame.set(width=14.22).move_to(ORIGIN)

    # ---------- 1. the sentence ----------
    def shot_sentence(self) -> None:
        self.reset_camera()
        self.words = VGroup(*[serif(t, 33) for t in TOKENS]).arrange(RIGHT, buff=0.27)
        self.words.move_to([0, 0.25, 0])
        self.play(
            LaggedStart(*[FadeIn(w, shift=0.12 * UP) for w in self.words], lag_ratio=0.11, run_time=2.4)
        )
        it = self.words[IT]
        self.box = RoundedRectangle(
            corner_radius=0.12,
            width=it.width + 0.34,
            height=it.height + 0.3,
            stroke_color=YELLOW,
            stroke_width=1.7,
        ).move_to(it)
        self.qmark = serif("?", 46, YELLOW).next_to(it, UP, buff=0.22)
        self.play(it.animate.set_color(YELLOW), Create(self.box), run_time=0.9)
        self.play(FadeIn(self.qmark, shift=0.1 * UP), run_time=0.6)
        self.camera.frame.save_state()
        self.play(self.camera.frame.animate.set(width=11.4).move_to([0.9, 0.25, 0]), run_time=2.6)
        self.play(Indicate(it, color=YELLOW, scale_factor=1.18), run_time=1.3)

    # ---------- 2. a word is a direction ----------
    def shot_vector(self) -> None:
        it = self.words[IT]
        others = VGroup(*[w for i, w in enumerate(self.words) if i != IT])
        self.play(
            self.camera.frame.animate.set(width=14.22).move_to(ORIGIN),
            FadeOut(others),
            FadeOut(self.qmark),
            FadeOut(self.box),
            it.animate.move_to([-5.3, 2.0, 0]),
            run_time=1.2,
        )
        plane = NumberPlane(
            x_range=[-6, 7, 1],
            y_range=[-3.5, 3, 1],
            background_line_style={"stroke_color": "#1E232B", "stroke_width": 1, "stroke_opacity": 0.75},
            axis_config={"stroke_opacity": 0},
        )
        vals = np.random.default_rng(5).uniform(0.05, 1.0, 12)
        strip = VGroup(
            *[
                Square(0.2, stroke_width=0.6, stroke_color="#2D333C").set_fill(CREAM, 0.1 + 0.55 * v)
                for v in vals
            ]
        ).arrange(DOWN, buff=0.035)
        strip.move_to([-4.9, -0.65, 0])
        count = serif("12,288 numbers", 22, MUTED).next_to(strip, DOWN, buff=0.24)
        arrow = vec([-4.9, 0.45, 0], [-1.4, 1.55, 0], CREAM, width=5.4)
        direction = serif("a direction", 30, CREAM).move_to([0.7, 1.9, 0])
        self.play(FadeIn(plane, run_time=1.0), it.animate.set_color(CREAM))
        self.play(FadeIn(strip, shift=0.1 * UP), FadeIn(count), run_time=0.8)
        self.play(Transform(strip, arrow), FadeOut(count), run_time=1.6)
        self.play(Write(direction), run_time=0.9)
        self.play(Indicate(arrow, color=CREAM, scale_factor=1.04), run_time=1.0)

    # ---------- 3. query, key, value ----------
    def shot_qkv(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.6)
        xs = [-4.3, 0.0, 4.3]
        colors = [BLUE, RED, GREEN]
        names = ["query", "key", "value"]
        self.panel = []
        for x, c, name in zip(xs, colors, names):
            a = vec([x - 0.9, -0.85, 0], [x + 0.75, 0.95, 0], c, width=5.2)
            label = serif(name, 32, c).move_to([x, 1.85, 0])
            self.panel.append(VGroup(a, label))
        self.play(
            LaggedStart(*[FadeIn(p, shift=0.15 * UP) for p in self.panel], lag_ratio=0.25, run_time=2.2)
        )
        self.play(
            LaggedStart(
                *[Indicate(p[0], color=p[1].get_color(), scale_factor=1.04) for p in self.panel],
                lag_ratio=0.4,
                run_time=2.2,
            )
        )

    # ---------- 4. what each one means ----------
    def shot_roles(self) -> None:
        meanings = [
            ("what am I", "looking for?"),
            ("what another word", "can offer"),
            ("the information", "itself"),
        ]
        groups = []
        for (line1, line2), x in zip(meanings, [-4.3, 0.0, 4.3]):
            g = VGroup(serif(line1, 21, MUTED), serif(line2, 21, MUTED)).arrange(DOWN, buff=0.1)
            g.move_to([x, -1.75, 0])
            groups.append(g)
        self.play(LaggedStart(*[FadeIn(g, shift=0.1 * UP) for g in groups], lag_ratio=0.3, run_time=2.0))

    # ---------- 5. the dot product ----------
    def shot_dot(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.6)
        plane = NumberPlane(
            x_range=[-7, 7, 1],
            y_range=[-4, 4, 1],
            background_line_style={"stroke_color": "#191E25", "stroke_width": 1, "stroke_opacity": 0.85},
            axis_config={"stroke_opacity": 0},
        )
        origin = np.array([-3.6, -1.9, 0.0])
        q_end = origin + np.array([3.6, 2.4, 0.0])
        q_arrow = vec(origin, q_end, BLUE, width=5.6)
        q_lab = MathTex(r"\vec{q}", font_size=40, color=BLUE).next_to(q_end, RIGHT, buff=0.14)
        self.play(FadeIn(plane), FadeIn(q_arrow), FadeIn(q_lab), run_time=0.8)

        ang = ValueTracker(np.deg2rad(-20))
        k_len = 4.5
        q_vec = q_end - origin

        def k_end():
            a = ang.get_value()
            return origin + k_len * np.array([np.cos(a), np.sin(a), 0.0])

        k_arrow = always_redraw(lambda: vec(origin, k_end(), RED, width=5.6))
        k_lab = always_redraw(
            lambda: MathTex(r"\vec{k}", font_size=40, color=RED).next_to(k_end(), RIGHT, buff=0.12)
        )

        def foot():
            kv = k_end() - origin
            u = kv / np.linalg.norm(kv)
            return origin + np.dot(q_vec, u) * u

        shadow_band = always_redraw(
            lambda: Line(origin, foot(), color=YELLOW, stroke_width=13, stroke_opacity=0.28)
        )
        shadow_line = always_redraw(
            lambda: Line(origin, foot(), color=YELLOW, stroke_width=2.4, stroke_opacity=0.95)
        )
        drop = always_redraw(
            lambda: DashedLine(q_end, foot(), color=YELLOW, stroke_width=2.2, dash_length=0.1)
        )
        self.play(FadeIn(k_arrow), FadeIn(k_lab), run_time=0.6)
        self.play(FadeIn(shadow_band), FadeIn(shadow_line), FadeIn(drop), run_time=0.6)

        formula = MathTex(r"\vec{q}\cdot\vec{k}\;=\;|\vec{q}|\,|\vec{k}|\cos\theta", font_size=40, color=CREAM)
        formula.move_to([3.4, 2.65, 0])
        shadow_title = serif("the shadow", 24, YELLOW).move_to([4.6, -0.6, 0])
        self.play(Write(formula), run_time=1.2)

        samples = [0.0, 0.25, 0.5, 0.75, 1.0]
        vals = []
        for t in samples:
            a = np.deg2rad(-20 + 28 * t)
            kv = k_len * np.array([np.cos(a), np.sin(a), 0.0])
            vals.append(float(np.dot(q_vec, kv)))
        numbers = [MathTex(f"{v:.1f}", font_size=38, color=YELLOW) for v in vals]
        readout = VGroup(MathTex(r"\vec{q}\cdot\vec{k}= ", font_size=34, color=CREAM), numbers[0])
        readout.arrange(RIGHT, buff=0.1).move_to([4.0, -2.3, 0])
        for n in numbers:
            n.move_to(readout[1])
        self.play(FadeIn(readout), FadeIn(shadow_title), run_time=0.4)

        step = 1.35
        for i in range(1, len(samples)):
            self.play(
                ang.animate.set_value(np.deg2rad(-20 + 28 * samples[i])),
                Transform(readout[1], numbers[i]),
                run_time=step,
                rate_func=smooth,
            )
        self.wait(0.2)

    # ---------- 6. three regimes ----------
    def shot_alignments(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.6)
        configs = [
            ("aligned", 32, 34, "+", GREEN),
            ("unrelated", 30, 120, "0", MUTED),
            ("opposite", 30, 210, "-", RED),
        ]
        xs = [-4.4, 0.0, 4.4]
        groups = []
        for (name, a1, a2, sign, col), x in zip(configs, xs):
            o = np.array([x, -0.7, 0.0])
            v1 = o + 1.55 * np.array([np.cos(np.deg2rad(a1)), np.sin(np.deg2rad(a1)), 0])
            v2 = o + 1.55 * np.array([np.cos(np.deg2rad(a2)), np.sin(np.deg2rad(a2)), 0])
            pair = VGroup(vec(o, v1, BLUE, width=4.2), vec(o, v2, RED, width=4.2))
            name_lab = serif(name, 26, CREAM).move_to([x, -2.25, 0])
            sign_lab = MathTex(sign, font_size=52, color=col).move_to([x, 1.15, 0])
            groups.append(VGroup(pair, name_lab, sign_lab))
        self.play(LaggedStart(*[FadeIn(g, shift=0.12 * UP) for g in groups], lag_ratio=0.3, run_time=2.4))

    # ---------- 7. the attention pattern ----------
    def grid_pos(self, i: int, j: int) -> np.ndarray:
        return np.array([0.30 + (j - 4.5) * 0.52, -0.30 - (i - 4.5) * 0.52, 0.0])

    def shot_grid(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.6)
        lo, hi = SCORES.min(), SCORES.max()
        cells = VGroup()
        self.cells = []
        for i in range(10):
            row = []
            for j in range(10):
                t = (SCORES[i, j] - lo) / (hi - lo)
                color = interpolate_color(ManimColor("#141A21"), ManimColor(YELLOW), float(t))
                cell = Square(0.52, stroke_width=0.8, stroke_color="#262C35")
                cell.set_fill(color, opacity=0.25 + 0.75 * float(t))
                cell.move_to(self.grid_pos(i, j))
                row.append(cell)
                cells.add(cell)
            self.cells.append(row)
        title = serif("attention pattern", 36, CREAM).move_to([-3.55, 3.3, 0])
        title.align_to(np.array([-3.55, 0, 0]), LEFT)
        rows = VGroup(
            *[serif(TOKENS[i], 16, MUTED).next_to(self.cells[i][0], LEFT, buff=0.1) for i in range(10)]
        )
        cols = VGroup()
        for j in range(10):
            lab = serif(TOKENS[j], 15, MUTED).rotate(PI / 4)
            lab.move_to(self.cells[0][j].get_top() + UP * 0.26 + LEFT * 0.11)
            cols.add(lab)
        self.play(FadeIn(title), run_time=0.6)
        order = sorted([(i, j) for i in range(10) for j in range(10)], key=lambda p: p[0] + p[1])
        self.play(
            LaggedStart(*[FadeIn(self.cells[i][j], scale=0.92) for i, j in order], lag_ratio=0.012, run_time=3.2)
        )
        self.play(FadeIn(rows), FadeIn(cols), run_time=0.7)
        row_box = SurroundingRectangle(VGroup(*self.cells[IT]), color=YELLOW, buff=0.035, stroke_width=2)
        col_box = SurroundingRectangle(
            VGroup(*[self.cells[i][ANIMAL] for i in range(10)]), color=GREEN, buff=0.035, stroke_width=1.6
        )
        self.play(
            Create(row_box),
            rows[IT].animate.set_color(YELLOW).scale(1.15),
            Create(col_box),
            rows[ANIMAL].animate.set_color(GREEN).scale(1.15),
            run_time=1.1,
        )
        self.row_box, self.col_box = row_box, col_box

    # ---------- 8. causal mask ----------
    def shot_mask(self) -> None:
        x0 = self.grid_pos(0, 0)[0] - 0.26
        x1 = self.grid_pos(0, 9)[0] + 0.26
        y0 = self.grid_pos(0, 0)[1] + 0.26
        y1 = self.grid_pos(9, 9)[1] - 0.26
        cover = Polygon(
            [x0, y0, 0], [x1, y0, 0], [x1, y1, 0], stroke_width=0, fill_color=BG, fill_opacity=0.975
        )
        diag = DashedLine([x0, y0, 0], [x1, y1, 0], color=MUTED, stroke_width=2, dash_length=0.09)
        note = serif("no peeking ahead", 26, MUTED).move_to([3.75, 2.35, 0])
        self.play(FadeIn(cover), Create(diag), FadeIn(note, shift=0.1 * DOWN), run_time=1.8)
        self.play(Indicate(note, color=CREAM, scale_factor=1.06), run_time=1.0)

    # ---------- 9. softmax ----------
    def shot_softmax(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.7)
        base = -1.95
        xs = [(-4.5) * 0.64 + j * 0.64 for j in range(10)]
        bars, labels = VGroup(), VGroup()
        for j in range(10):
            h = 0.02
            bar = Rectangle(width=0.5, height=h, stroke_width=0, fill_color=BLUE, fill_opacity=0.9)
            bar.move_to([xs[j], base + h / 2, 0])
            bars.add(bar)
            lab = serif(TOKENS[j], 14, MUTED if j > IT else CREAM).rotate(PI / 5)
            lab.move_to([xs[j] - 0.06, base - 0.34, 0])
            labels.add(lab)
        self.play(FadeIn(bars), FadeIn(labels), run_time=0.6)

        exp_h = np.exp(SCORES[IT] - SCORES[IT].max()) * 2.35
        exp_h[IT + 1 :] = 0.02
        grown = VGroup()
        for j in range(10):
            hh = max(0.02, exp_h[j])
            g = Rectangle(width=0.5, height=hh, stroke_width=0, fill_color=BLUE, fill_opacity=0.9)
            g.move_to([xs[j], base + hh / 2, 0])
            grown.add(g)
        self.play(Transform(bars, grown), run_time=2.2)

        final_h = np.maximum(WEIGHTS * 3.7, 0.02)
        final = VGroup()
        for j in range(10):
            col = interpolate_color(ManimColor(BLUE), ManimColor(YELLOW), float(WEIGHTS[j] / WEIGHTS.max()))
            f = Rectangle(width=0.5, height=final_h[j], stroke_width=0, fill_color=col, fill_opacity=0.95)
            f.move_to([xs[j], base + final_h[j] / 2, 0])
            final.add(f)
        self.play(Transform(bars, final), run_time=2.0)

        formula = MathTex(r"\mathrm{softmax}(x)_i=\frac{e^{x_i}}{\sum_j e^{x_j}}", font_size=38, color=CREAM)
        formula.move_to([3.9, 2.55, 0])
        self.play(Write(formula), run_time=1.3)

        top = np.argsort(WEIGHTS)[::-1][:3]
        pcts = VGroup()
        for j in top:
            p = MathTex(rf"{WEIGHTS[j]*100:.0f}\%", font_size=26, color=YELLOW)
            p.next_to(bars[j], UP, buff=0.1)
            pcts.add(p)
        self.play(LaggedStart(*[FadeIn(p, shift=0.08 * UP) for p in pcts], lag_ratio=0.25, run_time=0.9))
        self.bars = bars

    # ---------- 10. mixing the values ----------
    def shot_mix(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.6)
        origin = np.array([-2.7, -2.4, 0.0])
        angles = np.linspace(10, 165, 10)
        full = VGroup()
        for j in range(10):
            a = np.deg2rad(angles[j])
            v = 2.9 * np.array([np.cos(a), np.sin(a), 0.0])
            hi = j == ANIMAL
            full.add(vec(origin, origin + v, YELLOW if hi else GREEN, width=3.0 if hi else 2.6, opacity=0.55 if hi else 0.32))
        a_top = np.deg2rad(angles[ANIMAL])
        top_tip = origin + 2.9 * np.array([np.cos(a_top), np.sin(a_top), 0.0])
        top_lab = serif("animal's value", 20, YELLOW).next_to(top_tip, UP, buff=0.12)
        self.play(FadeIn(full), FadeIn(top_lab, shift=0.08 * UP), run_time=0.8)

        order = [int(j) for j in np.argsort(WEIGHTS)[::-1] if WEIGHTS[j] > 0.005]
        cursor = origin.copy()
        chain = VGroup()
        for j in order:
            a = np.deg2rad(angles[j])
            step = WEIGHTS[j] * 5.0 * np.array([np.cos(a), np.sin(a), 0.0])
            seg = vec(cursor, cursor + step, GREEN, width=3.6, opacity=0.95)
            chain.add(seg)
            cursor = cursor + step
        self.play(LaggedStart(*[GrowArrow(s) for s in chain], lag_ratio=0.22, run_time=3.0))

        context = vec(origin, cursor, CREAM, width=7.0)
        ctx_lab = serif("context", 28, CREAM).next_to(cursor, RIGHT, buff=0.18)
        self.play(GrowArrow(context), FadeIn(ctx_lab), run_time=1.0)
        formula = MathTex(r"\text{context}\;=\;\sum_i w_i\,\vec{v}_i", font_size=40, color=CREAM)
        formula.move_to([3.7, 2.6, 0])
        self.play(Write(formula), run_time=1.2)

    # ---------- 11. the answer ----------
    def shot_answer(self) -> None:
        self.play(FadeOut(*self.mobjects), run_time=0.7)
        words = VGroup(
            *[
                serif(t, 33, YELLOW if i == IT else (GREEN if i == ANIMAL else CREAM))
                for i, t in enumerate(TOKENS)
            ]
        ).arrange(RIGHT, buff=0.25).move_to([0, -0.1, 0])
        self.play(FadeIn(words, shift=0.1 * UP), run_time=1.0)
        it, animal = words[IT], words[ANIMAL]
        arc = CurvedArrow(
            animal.get_top() + UP * 0.12,
            it.get_top() + UP * 0.12,
            angle=-PI / 1.7,
            color=YELLOW,
            stroke_width=2.4,
            tip_length=0.18,
        )
        weight = MathTex(rf"{WEIGHTS[ANIMAL]:.2f}", font_size=30, color=YELLOW).move_to(
            arc.point_from_proportion(0.5) + UP * 0.28
        )
        self.play(Create(arc), FadeIn(weight), run_time=1.6)
        title = serif("attention is learned alignment", 44, CREAM).move_to([0, 3.15, 0])
        self.play(Write(title), run_time=1.8)
        self.play(Indicate(arc, color=YELLOW, scale_factor=1.05), run_time=1.2)
        self.wait(1.0)
