from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.voice.subtitle_bands import check_ass_band, parse_ass

ASS = """[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Bilingual,Arial,34,&H00231E1B,&H00231E1B,&H00F7FAFB,&H00F7FAFB,1,0,0,0,100,100,0,0,1,1.4,0,2,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

BANDS = """schema_version: 1
canvas: [1920, 1080]
picture_bands:
  conclusion: [840, 920]
  footer: [920, 950]
subtitle_band: [960, 1060]
"""

READABLE = BANDS + """readability:
  min_font_size: 30
  max_outline: 1.4
  max_outline_cjk: 1.0
"""


def cue(y: int, start: str = "0:00:00.00") -> str:
    return (
        f"Dialogue: 0,{start},0:00:05.00,Bilingual,,0,0,0,,"
        "{\\an2\\pos(960," + str(y) + ")}English line\\N{\\fnMicrosoft YaHei\\fs34\\bord0.9}中文行\n"
    )


class SubtitleBandTest(unittest.TestCase):
    def _check(self, dialogue: str, bands: str = BANDS) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ass = root / "subtitles.ass"
            band_path = root / "bands.yaml"
            ass.write_text(ASS + dialogue, encoding="utf-8")
            band_path.write_text(bands, encoding="utf-8")
            return check_ass_band(ass, band_path)

    def test_cue_inside_the_band_passes(self):
        report = self._check(cue(1050))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["cues"], 1)
        self.assertGreater(report["subtitle_band"][0], report["picture_max_bottom"])

    def test_cue_over_the_picture_fails(self):
        # y=930 puts the block top near 850, on the conclusion band.
        report = self._check(cue(930))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["violations"][0]["index"], 1)

    def test_cue_without_position_cannot_be_verified(self):
        dialogue = (
            "Dialogue: 0,0:00:00.00,0:00:05.00,Bilingual,,0,0,0,,{\\an2}"
            "English\\N{\\fnMicrosoft YaHei\\fs30}中文\n"
        )
        report = self._check(dialogue)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("no \\pos", report["violations"][0]["detail"])

    def test_picture_band_overlapping_subtitles_fails_before_parsing(self):
        bad = BANDS.replace("footer: [920, 950]", "footer: [920, 980]")
        report = self._check(cue(1050), bad)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("picture bands end", report["detail"])

    def test_parse_reads_anchor_lines_and_sizes(self):
        art = parse_ass(ASS + cue(1050))
        self.assertEqual(len(art), 1)
        self.assertEqual(art[0]["y"], 1050)
        self.assertEqual(art[0]["lines"], 2)
        self.assertEqual(art[0]["font_sizes"], [34.0, 34.0])
        self.assertEqual(art[0]["outlines"], [1.4, 0.9])
        self.assertAlmostEqual(art[0]["height"], 34 * 1.2 * 2)

    def test_readable_caption_passes_the_readability_rules(self):
        report = self._check(cue(1050), READABLE)
        self.assertEqual(report["status"], "PASS")

    def test_cjk_outline_above_the_ceiling_fails(self):
        dialogue = (
            "Dialogue: 0,0:00:00.00,0:00:05.00,Bilingual,,0,0,0,,"
            "{\\an2\\pos(960,1050)}English\\N{\\fnMicrosoft YaHei\\fs34\\bord1.4}中文行\n"
        )
        report = self._check(dialogue, READABLE)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("outline", report["violations"][0]["detail"])

    def test_cjk_font_below_the_floor_fails(self):
        dialogue = (
            "Dialogue: 0,0:00:00.00,0:00:05.00,Bilingual,,0,0,0,,"
            "{\\an2\\pos(960,1050)}English\\N{\\fnMicrosoft YaHei\\fs28\\bord0.9}中文行\n"
        )
        report = self._check(dialogue, READABLE)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("font", report["violations"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
