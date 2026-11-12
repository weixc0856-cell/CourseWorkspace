from __future__ import annotations

import unittest
from types import SimpleNamespace

from course_control.voice.narration_course import _voice_config


class VoiceConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lesson = SimpleNamespace(narration=SimpleNamespace(mode="reference_only"))
        self.tts = {
            "voice_ref": "zh.wav",
            "prompt_text": "中文参考",
            "voice_ref_en": "en.wav",
            "prompt_text_en": "English reference",
        }

    def test_chinese_script_uses_chinese_reference(self) -> None:
        path, prompt, mode = _voice_config(self.lesson, self.tts, "zh")
        self.assertEqual(str(path).replace("\\", "/"), "zh.wav")
        self.assertEqual(prompt, "中文参考")
        self.assertEqual(mode, "reference_only")

    def test_english_script_uses_english_reference(self) -> None:
        path, prompt, _ = _voice_config(self.lesson, self.tts, "en")
        self.assertEqual(str(path).replace("\\", "/"), "en.wav")
        self.assertEqual(prompt, "English reference")


if __name__ == "__main__":
    unittest.main()
