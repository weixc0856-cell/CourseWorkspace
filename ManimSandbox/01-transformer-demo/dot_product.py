"""点积的几何直觉：分量乘积之和 = 投影长度 × 被投影向量长度。

渲染：
    uv run manim -ql 01-transformer-demo/dot_product.py DotProduct
产物：
    media/videos/dot_product/480p15/DotProduct.mp4
"""

from manim import *

# 麦肯锡商务橙白预设（与 CourseSlides/css/mckinsey-orange.css 对齐）
config.background_color = "#FFFFFF"
MK_ORANGE = "#EB6100"
MK_TEXT = "#1A1A1A"
MK_MUTED = "#595959"
MK_BORDER = "#E5E5E5"
MK_FONT = "Segoe UI"  # 主题字体栈在 Windows 上的落点


class DotProduct(Scene):
    """a = (1, 3)，b = (3, 1)：a·b = 3 + 3 = 6，a 在 b 上的投影为 0.6·b。"""

    def construct(self):
        title = Text("Dot Product", font=MK_FONT, font_size=44, weight=BOLD, color=MK_TEXT)
        title.to_edge(UP, buff=0.55)
        self.play(Write(title))

        axes = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 4, 1],
            x_length=5.0,
            y_length=5.0,
            tips=False,
            axis_config={"color": MK_BORDER, "stroke_width": 2},
        ).shift(LEFT * 1.9 + DOWN * 0.3)
        axis_labels = axes.get_axis_labels(
            x_label=Text("x", font=MK_FONT, font_size=28, color=MK_MUTED),
            y_label=Text("y", font=MK_FONT, font_size=28, color=MK_MUTED),
        )
        self.play(Create(axes), FadeIn(axis_labels))

        vec_a = Arrow(axes.c2p(0, 0), axes.c2p(1, 3), buff=0, color=MK_ORANGE, stroke_width=7)
        vec_b = Arrow(axes.c2p(0, 0), axes.c2p(3, 1), buff=0, color=MK_TEXT, stroke_width=7)
        label_a = Text("a = (1, 3)", font=MK_FONT, font_size=26, color=MK_ORANGE)
        label_a.next_to(vec_a.get_end(), UP, buff=0.18)
        label_b = Text("b = (3, 1)", font=MK_FONT, font_size=26, color=MK_TEXT)
        label_b.next_to(vec_b.get_end(), RIGHT, buff=0.2)
        self.play(GrowArrow(vec_a), GrowArrow(vec_b), FadeIn(label_a), FadeIn(label_b))

        # 投影：t = (a·b)/|b|² = 6/10 = 0.6
        proj_point = axes.c2p(1.8, 0.6)
        proj = DashedLine(
            axes.c2p(0, 0), proj_point, color=MK_ORANGE, stroke_width=4, dash_length=0.16
        )
        proj_dot = Dot(proj_point, color=MK_ORANGE, radius=0.07)
        drop = DashedLine(
            axes.c2p(1, 3), proj_point, color=MK_MUTED, stroke_width=2, dash_length=0.1
        )
        self.play(Create(drop), Create(proj), FadeIn(proj_dot), run_time=1.0)

        panel = VGroup(
            Text("a · b = 1×3 + 3×1 = 6", font=MK_FONT, font_size=28, color=MK_TEXT),
            Text("projection = 0.6 · b", font=MK_FONT, font_size=28, color=MK_ORANGE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        panel.move_to(UP * 0.9).to_edge(RIGHT, buff=0.7)
        self.play(Write(panel))

        self.wait(2.5)
