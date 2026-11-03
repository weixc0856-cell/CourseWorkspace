"""环境自检场景：麦肯锡橙白配色能否正常出图。

渲染：
    .venv/Scripts/Activate.ps1              # 或直接 uv run
    manim -ql 01-transformer-demo/test_demo.py TestDemo
产物：
    media/videos/test_demo/480p15/TestDemo.mp4
"""

from manim import *

# 麦肯锡商务橙白预设（与 CourseSlides/css/mckinsey-orange.css 对齐）
config.background_color = "#FFFFFF"
MK_ORANGE = "#EB6100"
MK_TEXT = "#1A1A1A"
MK_GRAY = "#8C8C8C"


class TestDemo(Scene):
    def construct(self):
        text = Text("McKinsey Orange & White Demo", color=MK_TEXT, font_size=36)
        accent_box = SurroundingRectangle(text, color=MK_ORANGE, buff=0.3, stroke_width=3)
        self.play(Write(text))
        self.play(Create(accent_box))
        self.wait(1)
