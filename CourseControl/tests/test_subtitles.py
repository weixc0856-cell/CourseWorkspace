from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.voice.subtitles import (
    BilingualCue,
    BilingualDraft,
    CuePolicy,
    retime_draft,
    _wrap,
    _wrap_zh,
    rewrap_srt,
    build_subtitles,
    plan_cues,
    validate_cues,
    write_ass,
    write_srt,
    write_vtt,
)


class Segment:
    def __init__(self, id: str, text: str):
        self.id = id
        self.text = text
        self.style = None
        self.pause_after_ms = 300


class Page:
    def __init__(self, slide: int, segments):
        self.slide = slide
        self.segments = segments
        self.target_seconds = 10.0


class Script:
    def __init__(self, pages):
        self.pages = pages
        self.language = "en"
        self.policy = {"page_pause_ms": 600}


META = {
    "assembly": {"duration_s": 5.0},
    "segments": [
        {"segment_id": "s1", "slide": 1, "start_s": 0.0, "duration_s": 5.0},
    ],
}


class FakeClient:
    route = SimpleNamespace(provider="local", model="fake")

    def chat(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"].split("\n", 1)[1])
        cues = [{"index": item["index"], "zh": f"第{item['index']}句中文。"} for item in payload]
        return json.dumps({"cues": cues}, ensure_ascii=False)


class CuePlanTest(unittest.TestCase):
    def test_sentences_become_cues(self):
        script = Script([Page(1, [Segment("s1", "This is one sentence. This is another sentence.")])])
        cues = plan_cues(script, META, CuePolicy(), 30.0)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["segment_id"], "s1")
        self.assertGreater(cues[1]["start_ms"], cues[0]["start_ms"])
        self.assertLessEqual(cues[0]["end_ms"], cues[1]["start_ms"])

    def test_short_segment_merges(self):
        meta = {
            "assembly": {"duration_s": 1.2},
            "segments": [{"segment_id": "s1", "slide": 1, "start_s": 0.0, "duration_s": 1.2}],
        }
        script = Script([Page(1, [Segment("s1", "One. Two. Three. Four.")])])
        cues = plan_cues(script, meta, CuePolicy(), 30.0)
        self.assertLessEqual(len(cues), 2)

    def test_validation_flags_bad_cue(self):
        cues = [
            {
                "index": 1,
                "slide": 1,
                "segment_id": "s1",
                "start_ms": 0,
                "end_ms": 500,
                "en": "Short",
                "zh": "长" * 40,
                "en_lines": ["Short"],
                "zh_lines": ["长" * 15, "长" * 15, "长" * 10],
            }
        ]
        problems = validate_cues(cues, CuePolicy(), 30.0, 5000)
        self.assertTrue(problems)


class WrapTest(unittest.TestCase):
    def test_english_wrap(self):
        lines = _wrap("word " * 30, 42, 2)
        self.assertTrue(all(len(line) <= 42 for line in lines))

    def test_chinese_wrap(self):
        lines = _wrap_zh("这是一个很长的中文字幕句子，" * 4, 15, 2)

    def test_chinese_wrap_does_not_split_words_or_start_with_punctuation(self):
        lines = _wrap_zh("因此该层仍为每个位置产生单一表示，随后进入下一层。", 15, 2)
        self.assertFalse(any(line.endswith("表") for line in lines[:-1]))
        self.assertFalse(any(line.startswith(("，", "。", "、", "；")) for line in lines[1:]))

    def test_rewrap_keeps_timing_and_wraps_chinese(self):
        source = """1
00:00:00,000 --> 00:00:05,000
因此该层仍为每个位置产生单一表示，随后进入下一层。
"""
        result = rewrap_srt(source, CuePolicy(), bilingual=False)
        self.assertIn("00:00:00,000 --> 00:00:05,000", result)
        body = [line for line in result.splitlines()[2:] if line.strip()]
        self.assertTrue(all(len(line) <= 15 for line in body))
        self.assertEqual("".join(body), "因此该层仍为每个位置产生单一表示，随后进入下一层。")


class WriterTest(unittest.TestCase):
    def test_srt_vtt_ass(self):
        cues = [
            {
                "index": 1,
                "slide": 1,
                "segment_id": "s1",
                "start_ms": 0,
                "end_ms": 2000,
                "en": "Hello",
                "zh": "你好",
                "en_lines": ["Hello"],
                "zh_lines": ["你好"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_srt(cues, root / "a.srt")
            write_vtt(cues, root / "a.vtt")
            write_ass(cues, root / "a.ass", 1920, 1080)
            self.assertIn("Hello", (root / "a.srt").read_text(encoding="utf-8"))
            self.assertTrue((root / "a.vtt").read_text(encoding="utf-8").startswith("WEBVTT"))
            ass = (root / "a.ass").read_text(encoding="utf-8")
            self.assertIn("Dialogue:", ass)
            self.assertIn("Microsoft YaHei", ass)


class BuildSubtitleTest(unittest.TestCase):
    def test_build_draft(self):
        script = Script([Page(1, [Segment("s1", "This is one sentence. This is another sentence.")])])
        paths = SimpleNamespace(
            slug="test-lesson",
            build_root=Path(tempfile.mkdtemp()),
            lesson=SimpleNamespace(
                outputs=SimpleNamespace(fps=30),
                subtitles=SimpleNamespace(top_language="en", bottom_language="zh-Hans"),
            ),
        )
        draft, srt = build_subtitles(Path("."), paths, script, META, FakeClient())
        self.assertEqual(len(draft.cues), 2)
        self.assertTrue(srt.is_file())
        self.assertTrue((paths.build_root / "subtitles" / "bilingual.draft.json").is_file())


if __name__ == "__main__":
    unittest.main()


class AsrRetimeTest(unittest.TestCase):
    def draft(self):
        cues = [
            BilingualCue(
                index=index,
                slide=1,
                segment_id="seg_1",
                start_ms=start,
                end_ms=start + 2000,
                en=text,
                zh=text,
                en_lines=[text],
                zh_lines=[text],
            )
            for index, (start, text) in enumerate(
                [(0, "alpha beta"), (5000, "gamma delta")], start=1
            )
        ]
        return BilingualDraft(
            lesson="demo",
            languages={"top": "en", "bottom": "zh-Hans"},
            policy={},
            cues=cues,
            counts={"cues": 2},
            translation={},
        )

    def test_speech_timestamps_move_the_cues(self):
        meta = {"segments": [{"segment_id": "seg_1", "start_s": 0.0, "duration_s": 10.0}]}
        words = [
            {"start_ms": 0, "end_ms": 300, "text": "alpha"},
            {"start_ms": 300, "end_ms": 600, "text": "beta"},
            {"start_ms": 7000, "end_ms": 7300, "text": "gamma"},
            {"start_ms": 7300, "end_ms": 7600, "text": "delta"},
        ]
        updated = retime_draft(self.draft(), meta, CuePolicy(), 30.0, asr_words=words)
        starts = [cue.start_ms for cue in updated.cues]
        self.assertEqual(starts[0], 0)
        self.assertGreaterEqual(starts[1], 6800)
        self.assertLessEqual(starts[1], 7200)

    def test_without_asr_words_the_old_allocation_is_kept(self):
        meta = {"segments": [{"segment_id": "seg_1", "start_s": 0.0, "duration_s": 10.0}]}
        updated = retime_draft(self.draft(), meta, CuePolicy(), 30.0)
        self.assertLess(updated.cues[1].start_ms, 7000)


class RebuildOnTimelineTest(unittest.TestCase):
    """The episode audio is in beat order; the SRT must follow the audio."""

    def _script(self):
        # Slide order is a, b, c; the episode plays a, c, b.
        return SimpleNamespace(
            pages=[
                Page(1, [Segment("a", "First slide speaks here.")]),
                Page(2, [Segment("b", "Second slide speaks here.")]),
                Page(3, [Segment("c", "Third slide speaks here.")]),
            ]
        )

    def _timing(self):
        return {
            "total_seconds": 15.0,
            "beats": [
                {"id": "B1", "seconds": 5.0, "segments": ["a"]},
                {"id": "B2", "seconds": 5.0, "segments": ["c"]},
                {"id": "B3", "seconds": 5.0, "segments": ["b"]},
            ],
        }

    def _meta(self, durations):
        return {
            "segments": [
                {"segment_id": key, "start_s": 0.0, "duration_s": value}
                for key, value in durations.items()
            ]
        }

    def _draft(self):
        def cue(index, segment, slide, text, zh):
            return {"index": index, "slide": slide, "segment_id": segment, "en": text, "zh": zh}

        return [
            cue(1, "a", 1, "First slide speaks here.", "第一张。"),
            cue(2, "b", 2, "Second slide speaks here.", "第二张。"),
            cue(3, "c", 3, "Third slide speaks here.", "第三张。"),
        ]

    def test_cues_follow_the_episode_order_not_the_slide_order(self):
        from course_control.voice.subtitles import rebuild_on_timeline

        cues, report = rebuild_on_timeline(
            self._script(),
            self._meta({"a": 5.0, "b": 5.0, "c": 5.0}),
            self._timing(),
            self._draft(),
            CuePolicy(),
            30.0,
        )
        self.assertEqual([cue["segment_id"] for cue in cues], ["a", "c", "b"])
        by_segment = {cue["segment_id"]: cue for cue in cues}
        self.assertEqual(by_segment["c"]["start_ms"], 5000)
        self.assertEqual(by_segment["b"]["start_ms"], 10000)
        self.assertEqual(report["first_start_ms"], 0)
        self.assertLessEqual(report["last_end_ms"], 15000)

    def test_mid_word_break_is_repaired_and_keeps_both_translations(self):
        from course_control.voice.subtitles import rebuild_on_timeline

        script = SimpleNamespace(pages=[Page(1, [Segment("a", "The fuel bill is removing one kilogram.")])])
        timing = {"total_seconds": 12.0, "beats": [{"id": "B1", "seconds": 12.0, "segments": ["a"]}]}
        draft = [
            {"index": 1, "slide": 1, "segment_id": "a", "en": "The fuel bill is removin", "zh": "油费相当于"},
            {"index": 2, "slide": 1, "segment_id": "a", "en": "g one kilogram.", "zh": "一公斤。"},
        ]
        cues, report = rebuild_on_timeline(
            script, self._meta({"a": 12.0}), timing, draft, CuePolicy(), 30.0
        )
        self.assertEqual(report["repaired_midword_breaks"], 1)
        english = " ".join(cue["en"] for cue in cues)
        chinese = "".join(cue["zh"] for cue in cues)
        self.assertEqual(english, "The fuel bill is removing one kilogram.")
        self.assertEqual(chinese, "油费相当于一公斤。")
        self.assertFalse(any(cue["en"].startswith("g ") for cue in cues))

    def test_beat_total_mismatch_is_rejected(self):
        from course_control.voice.subtitles import SubtitleError, rebuild_on_timeline

        with self.assertRaises(SubtitleError):
            rebuild_on_timeline(
                self._script(),
                self._meta({"a": 5.0, "b": 5.0, "c": 4.0}),
                self._timing(),
                self._draft(),
                CuePolicy(),
                30.0,
            )

    def test_english_split_never_cuts_a_word(self):
        from course_control.voice.subtitles import _best_split_en

        text = "is worth about the same fuel as removing one hundred and twenty-nine kilograms."
        cut = _best_split_en(text)
        self.assertGreater(cut, 0)
        self.assertLess(cut, len(text))
        self.assertFalse(text[cut - 1].isalnum() and text[cut].isalnum())
