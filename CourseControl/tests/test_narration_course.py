from __future__ import annotations

import unittest

from course_control.authoring.models import NarrationScript, ScriptPage, ScriptSegment
from course_control.voice.narration_course import (
    check_script_against_notes,
    dry_run,
    extract_page_texts,
)

NOTES = """### Slide 1: One

- **时长预算**：10 秒
- **动画切入**：无
- **技术核查**：none
- **逐字口播**：First sentence. Second sentence.

---

### Slide 2: Two

- **时长预算**：10 秒
- **动画切入**：无
- **技术核查**：none
- **逐字口播**：Third sentence.
"""


def script(text1: str = "First sentence. Second sentence.", text2: str = "Third sentence."):
    return NarrationScript(
        lesson="tts-test",
        pages=[
            ScriptPage(
                slide=1,
                target_seconds=10,
                segments=[ScriptSegment(id="s1", text=text1)],
            ),
            ScriptPage(
                slide=2,
                target_seconds=10,
                segments=[ScriptSegment(id="s2", text=text2)],
            ),
        ],
    )


class ExtractTest(unittest.TestCase):
    def test_extracts_prose_and_drops_separator(self):
        texts = extract_page_texts(NOTES)
        self.assertEqual(texts[0], "First sentence. Second sentence.")
        self.assertEqual(texts[1], "Third sentence.")

    def test_script_matches(self):
        check_script_against_notes(NOTES, script())

    def test_mismatch_raises(self):
        with self.assertRaises(Exception):
            check_script_against_notes(NOTES, script(text1="Different."))

    def test_dry_run_estimates(self):
        info = dry_run(script())
        self.assertGreater(info["estimated_audio_seconds"], 0)
        self.assertEqual(info["pages"], 2)
        self.assertEqual(info["segments"], 2)


if __name__ == "__main__":
    unittest.main()


class TtsOverrideContractTest(unittest.TestCase):
    def test_short_tts_override_is_rejected(self):
        from pydantic import ValidationError
        from course_control.authoring.models import ScriptSegment

        with self.assertRaises(ValidationError):
            ScriptSegment(
                id='s003-p1',
                text='Speed is where the arithmetic turns nasty. ' * 6,
                tts_text='Force grows with v squared.',
            )

    def test_full_length_tts_override_is_accepted(self):
        from course_control.authoring.models import ScriptSegment

        text = 'Speed is where the arithmetic turns nasty. ' * 3
        segment = ScriptSegment(id='s003-p1', text=text, tts_text=text.replace('nasty', 'ugly'))
        self.assertTrue(segment.tts_text)
