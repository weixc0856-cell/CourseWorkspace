from __future__ import annotations

import unittest

from course_control.subtitles_qc import check_cues, parse_srt


def cue(index: int, start: int, end: int, *lines: str) -> dict:
    return {"index": index, "start_ms": start, "end_ms": end, "lines": list(lines)}


class SubtitleQCTest(unittest.TestCase):
    def test_clean_bilingual_cues_pass(self) -> None:
        report = check_cues(
            [
                cue(1, 0, 3000, "Attention compares every pair.", "注意力比较每一对。"),
                cue(2, 3100, 6000, "The matrix is square.", "矩阵是方的。"),
            ],
            bilingual=True,
        )
        self.assertEqual(report["status"], "PASS", report)

    def test_missing_language_fails(self) -> None:
        report = check_cues([cue(1, 0, 3000, "Only English here.")], bilingual=True)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("bottom-language" in item for item in report["errors"]))

    def test_line_starting_with_punctuation_warns(self) -> None:
        report = check_cues(
            [cue(1, 0, 3000, "A clean line.", "，注意力比较每一对。")],
            bilingual=True,
        )
        self.assertEqual(report["status"], "WARN")
        self.assertTrue(any("starts with punctuation" in item for item in report["warnings"]))

    def test_term_split_across_cues_warns(self) -> None:
        glossary = {"attention": "注意力"}
        report = check_cues(
            [
                cue(1, 0, 3000, "We use at", "我们使用注意"),
                cue(2, 3100, 6000, "tention here.", "力。"),
            ],
            bilingual=True,
            glossary=glossary,
        )
        self.assertEqual(report["status"], "WARN")
        self.assertTrue(any("term split" in item for item in report["warnings"]))

    def test_number_split_across_lines_warns(self) -> None:
        report = check_cues(
            [cue(1, 0, 3000, "Published in 201", "7 by eight authors.")],
            bilingual=False,
        )
        self.assertEqual(report["status"], "WARN")
        self.assertTrue(any("number is split" in item for item in report["warnings"]))

    def test_overlap_is_an_error(self) -> None:
        report = check_cues(
            [cue(1, 0, 3000, "Hello."), cue(2, 2500, 5000, "Again.")],
            bilingual=False,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("overlaps" in item for item in report["errors"]))

    def test_parser_reads_standard_srt(self) -> None:
        text = (
            "1\n00:00:00,000 --> 00:00:02,000\nHello\n你好\n\n"
            "2\n00:00:02,100 --> 00:00:04,000\nWorld\n世界\n"
        )
        cues = parse_srt(text)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["end_ms"], 2000)
        self.assertEqual(cues[1]["lines"], ["World", "世界"])


if __name__ == "__main__":
    unittest.main()
