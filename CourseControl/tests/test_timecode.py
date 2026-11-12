from __future__ import annotations

import unittest

from course_control.content.timecode import (
    AudioAlignment,
    TimecodeError,
    align_audio_segment,
    format_srt_timestamp,
    frame_to_ms,
    frame_to_sample,
    frame_to_srt,
    ms_to_frame,
    parse_srt_timestamp,
    sample_to_frame,
    srt_to_frames,
)

FPS_CASES = [
    (24, 1, 42, 1000, "00:00:00,042"),
    (25, 1, 40, 1000, "00:00:00,040"),
    (30, 1, 33, 1000, "00:00:00,033"),
    (30000, 1001, 33, 1001, "00:00:00,033"),
    (60000, 1001, 17, 1001, "00:00:00,017"),
]


class FrameMillisecondTest(unittest.TestCase):
    def test_frame_to_ms_at_common_rates(self):
        for num, den, one_frame_ms, one_second_ms, _ in FPS_CASES:
            with self.subTest(fps=(num, den)):
                self.assertEqual(frame_to_ms(1, num, den), one_frame_ms)
                one_second_frames = round(num / den)
                self.assertEqual(
                    frame_to_ms(one_second_frames, num, den), one_second_ms
                )

    def test_frame_to_ms_exact_for_rational_rates(self):
        self.assertEqual(frame_to_ms(30, 30000, 1001), 1001)
        self.assertEqual(frame_to_ms(60, 60000, 1001), 1001)
        self.assertEqual(frame_to_ms(30, 60000, 1001), 501)
        self.assertEqual(frame_to_ms(1001, 30000, 1001), 33400)

    def test_ms_to_frame_rounds_half_up(self):
        self.assertEqual(ms_to_frame(1000, 24), 24)
        self.assertEqual(ms_to_frame(1000, 25), 25)
        self.assertEqual(ms_to_frame(1000, 30), 30)
        self.assertEqual(ms_to_frame(1000, 30000, 1001), 30)
        self.assertEqual(ms_to_frame(1000, 60000, 1001), 60)
        self.assertEqual(ms_to_frame(333, 30), 10)
        self.assertEqual(ms_to_frame(16, 60000, 1001), 1)

    def test_negative_and_zero_values_rejected(self):
        with self.assertRaises(TimecodeError):
            frame_to_ms(-1, 30)
        with self.assertRaises(TimecodeError):
            ms_to_frame(-1, 30)
        with self.assertRaises(TimecodeError):
            frame_to_ms(1, 0)
        with self.assertRaises(TimecodeError):
            frame_to_ms(1, 30, 0)
        with self.assertRaises(TimecodeError):
            frame_to_ms(True, 30)
        with self.assertRaises(TimecodeError):
            ms_to_frame(1.5, 30)


class SrtTest(unittest.TestCase):
    def test_frame_to_srt(self):
        self.assertEqual(frame_to_srt(0, 30), "00:00:00,000")
        self.assertEqual(frame_to_srt(1, 24), "00:00:00,042")
        self.assertEqual(frame_to_srt(30, 30000, 1001), "00:00:01,001")
        self.assertEqual(frame_to_srt(60, 60000, 1001), "00:00:01,001")

    def test_format_and_parse(self):
        self.assertEqual(format_srt_timestamp(3_661_001), "01:01:01,001")
        self.assertEqual(parse_srt_timestamp("01:01:01,001"), 3_661_001)
        self.assertEqual(parse_srt_timestamp("00:00:00,000"), 0)
        with self.assertRaises(TimecodeError):
            parse_srt_timestamp("00:00:01.000")
        with self.assertRaises(TimecodeError):
            parse_srt_timestamp("00:60:01,000")

    def test_srt_cue_to_frames(self):
        start, end = srt_to_frames("00:00:00,500", "00:00:07,300", 30)
        self.assertEqual((start, end), (15, 219))
        with self.assertRaises(TimecodeError):
            srt_to_frames("00:00:01,000", "00:00:01,000", 30)
        with self.assertRaises(TimecodeError):
            srt_to_frames("00:00:00,000", "00:00:00,001", 30)


class AudioAlignmentTest(unittest.TestCase):
    def test_48k_30fps_is_exact(self):
        frame = frame_to_sample(1, 48000, 30)
        self.assertEqual(frame, 1600)
        self.assertEqual(sample_to_frame(1600, 48000, 30), 1)
        alignment = align_audio_segment(1600, 48000, 48000, 30)
        self.assertIsInstance(alignment, AudioAlignment)
        self.assertEqual((alignment.start_frame, alignment.end_frame), (1, 30))
        self.assertEqual(alignment.start_drift_samples, 0)
        self.assertEqual(alignment.end_drift_samples, 0)
        self.assertTrue(alignment.within_one_frame())

    def test_2997_reports_drift_instead_of_hiding_it(self):
        alignment = align_audio_segment(1600, 48000, 48000, 30000, 1001)
        self.assertEqual((alignment.start_frame, alignment.end_frame), (1, 30))
        self.assertEqual(alignment.aligned_start_sample, 1602)
        self.assertEqual(alignment.aligned_end_sample, 48048)
        self.assertEqual(alignment.start_drift_samples, 2)
        self.assertEqual(alignment.end_drift_samples, 48)
        self.assertEqual(alignment.max_drift_samples, 1602)
        self.assertTrue(alignment.within_one_frame())

    def test_invalid_audio_segment_rejected(self):
        with self.assertRaises(TimecodeError):
            align_audio_segment(100, 100, 48000, 30)
        with self.assertRaises(TimecodeError):
            align_audio_segment(100, 90, 48000, 30)
        with self.assertRaises(TimecodeError):
            align_audio_segment(0, 1, 0, 30)
        with self.assertRaises(TimecodeError):
            align_audio_segment(-1, 48000, 48000, 30)


if __name__ == "__main__":
    unittest.main()
