from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.quality.speech_alignment import (
    FAIL,
    INCOMPLETE,
    PASS,
    _numbers,
    _numbers_match,
    _wer,
    evaluate,
    run_alignment,
)
from course_control.voice.alignment import Word


def word(start, end, text):
    return Word(start_ms=int(start * 1000), end_ms=int(end * 1000), text=text, probability=0.9)


class SpeechAlignmentTest(unittest.TestCase):
    def cues(self):
        return [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "en": "A test is accurate."},
            {"index": 2, "start_s": 2.2, "end_s": 4.0, "en": "You test positive."},
        ]

    def words(self):
        return [
            word(0.0, 0.3, "A"), word(0.3, 0.6, "test"), word(0.6, 0.9, "is"),
            word(1.6, 2.0, "accurate"),
            word(2.2, 2.5, "You"), word(2.5, 2.8, "test"), word(3.6, 4.0, "positive"),
        ]

    def test_perfect_alignment_passes(self):
        report = evaluate(self.cues(), self.words(), 4.0)
        self.assertEqual(report["status"], PASS, report)
        self.assertEqual(report["uncovered_speech"], [])

    def test_high_wer_fails(self):
        words = [word(0.1, 0.3, "Totally"), word(0.3, 0.5, "different"), word(0.5, 0.7, "words")]
        report = evaluate(self.cues(), words, 4.0)
        self.assertEqual(report["status"], FAIL)

    def test_timing_drift_fails(self):
        words = self.words()
        words[:4] = [
            word(0.5, 0.8, "A"), word(0.8, 1.1, "test"),
            word(1.1, 1.4, "is"), word(2.4, 2.6, "accurate"),
        ]
        report = evaluate(self.cues(), words, 4.0)
        self.assertTrue(any(item["timing_deviation_s"] > 0.35 for item in report["segments"]))

    def test_uncovered_speech_fails(self):
        words = self.words() + [word(4.5, 5.2, "extra"), word(5.2, 5.5, "speech")]
        report = evaluate(self.cues(), words, 5.5)
        self.assertEqual(report["status"], FAIL)
        self.assertTrue(report["uncovered_speech"])

    def test_missing_master_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = run_alignment(root / "missing.mp4", self.cues(), root / "script.json", root)
        self.assertEqual(report["status"], INCOMPLETE)

    def test_wer(self):
        self.assertEqual(_wer("a b c".split(), "a b c".split()), 0.0)
        self.assertAlmostEqual(_wer("a b c".split(), "a x c".split()), 1 / 3)

    def test_numeric_values_must_match(self):
        cues = [{"index": 1, "start_s": 0.0, "end_s": 3.0, "en": "0.99 times 0.01 equals 0.0099."}]
        words = [
            word(0.1, 0.4, "0.99"), word(0.5, 0.8, "times"),
            word(0.9, 1.2, "0.01"), word(1.3, 1.6, "equals"),
            word(1.7, 2.2, "990"),
        ]
        report = evaluate(cues, words, 3.0)
        self.assertFalse(report["segments"][0]["numeric_ok"])
        self.assertEqual(report["status"], FAIL)

    def test_percent_equivalence(self):
        reference = _numbers("1%")
        heard = _numbers("0.01")
        self.assertTrue(_numbers_match(reference, heard))

    def test_missing_or_extra_number_fails(self):
        self.assertFalse(_numbers_match(_numbers("0.0099"), _numbers("")))
        self.assertFalse(_numbers_match(_numbers("0.0099"), _numbers("0.0099 990")))
        self.assertFalse(_numbers_match(_numbers("0.0099"), _numbers("0.099")))

    def test_plain_text_still_uses_point_ten(self):
        cues = [{"index": 1, "start_s": 0.0, "end_s": 1.0, "en": "A test is accurate."}]
        words = [word(0.0, 0.2, "A"), word(0.2, 0.4, "test"), word(0.4, 0.6, "is"), word(0.6, 0.9, "wrong")]
        report = evaluate(cues, words, 1.0)
        self.assertEqual(report["segments"][0]["wer_max"], 0.10)


if __name__ == "__main__":
    unittest.main()
