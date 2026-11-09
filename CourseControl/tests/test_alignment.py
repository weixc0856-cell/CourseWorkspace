from __future__ import annotations

import unittest

from course_control.alignment import Word, align_cues


def word(start: int, end: int, text: str) -> Word:
    return Word(start_ms=start, end_ms=end, text=text, probability=0.95)


class AlignmentTests(unittest.TestCase):
    def test_exact_match_has_full_coverage(self) -> None:
        cues = [{"index": 1, "start_ms": 0, "end_ms": 2000, "en": "self attention starts here"}]
        words = [
            word(0, 400, "self"),
            word(400, 800, "attention"),
            word(800, 1200, "starts"),
            word(1200, 1600, "here"),
        ]
        result = align_cues(cues, words)
        self.assertEqual(result["mismatches"], [])
        self.assertEqual(result["mean_coverage"], 1.0)
        self.assertEqual(result["uncovered_speech"], [])

    def test_paragraph_mismatch_is_reported(self) -> None:
        cues = [{"index": 1, "start_ms": 0, "end_ms": 1500, "en": "query key value vector"}]
        words = [word(0, 500, "banana"), word(500, 1000, "orange")]
        result = align_cues(cues, words)
        self.assertEqual(len(result["mismatches"]), 1)
        self.assertLess(result["mismatches"][0]["coverage"], 0.6)

    def test_uncovered_speech_is_reported(self) -> None:
        cues = [{"index": 1, "start_ms": 0, "end_ms": 1000, "en": "hello"}]
        words = [
            word(0, 400, "hello"),
            word(3000, 3500, "this"),
            word(3500, 4000, "is"),
            word(4000, 4500, "missing"),
            word(4500, 5000, "speech"),
        ]
        result = align_cues(cues, words)
        self.assertEqual(len(result["uncovered_speech"]), 1)
        self.assertGreaterEqual(
            result["uncovered_speech"][0]["end_s"] - result["uncovered_speech"][0]["start_s"],
            1.5,
        )

    def test_subtitle_mentions_missing_from_speech(self) -> None:
        cues = [{"index": 1, "start_ms": 0, "end_ms": 1500, "en": "query key value vector"}]
        words = [word(0, 400, "query"), word(400, 800, "key")]
        result = align_cues(cues, words)
        self.assertEqual(len(result["mismatches"]), 1)


if __name__ == "__main__":
    unittest.main()
