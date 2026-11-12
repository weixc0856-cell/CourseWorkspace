from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.voice.subtitles import (
    CuePolicy,
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
