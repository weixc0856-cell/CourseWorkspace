from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.voice.audio import AudioAssetError, resolve_assets
from course_control.voice.audio import lexicon as lexicon_module
from course_control.voice.audio import voice_bible as voice_bible_module
from course_control.content.contracts import Narration
from course_control.voice.narrate import segment_cache_key
from course_control.platform.session import normalize_stream, sha256_text

LEXICON = {
    "schema_version": 1,
    "id": "automotive",
    "language": "en",
    "entries": [
        {"term": "CFD", "say": "C F D"},
        {"term": "Mercedes-Benz", "say": "Mercedes Benz"},
        {"term": "Reynolds", "say": "Renolds"},
    ],
}

BIBLE = {
    "schema_version": 1,
    "id": "wayne-en-v1",
    "language": "en",
    "ref_audio": "voice.wav",
    "prompt_text": "Welcome to this lesson.",
    "mode": "reference_only",
    "speed": 0.8,
}


class LexiconTest(unittest.TestCase):
    def _lexicon(self, entries: list[dict]):
        return lexicon_module.Lexicon.model_validate(
            {"schema_version": 1, "id": "demo", "entries": entries}
        )

    def test_rewrites_a_whole_word_only(self) -> None:
        lexicon = self._lexicon([{"term": "CFD", "say": "C F D"}])
        self.assertEqual(lexicon_module.apply(lexicon, "a CFD case").text, "a C F D case")
        self.assertEqual(
            lexicon_module.apply(lexicon, "CFDish").text, "CFDish"
        )

    def test_matches_case_insensitively_and_records_the_source_term(self) -> None:
        lexicon = self._lexicon([{"term": "Reynolds", "say": "Renolds"}])
        application = lexicon_module.apply(lexicon, "a reynolds number")
        self.assertEqual(application.text, "a Renolds number")
        self.assertEqual(application.applied, (("reynolds", "Renolds"),))

    def test_longest_term_wins_and_is_not_rewritten_twice(self) -> None:
        lexicon = self._lexicon(
            [
                {"term": "Benz", "say": "Bents"},
                {"term": "Mercedes-Benz", "say": "Mercedes Benz"},
            ]
        )
        application = lexicon_module.apply(lexicon, "a Mercedes-Benz sedan")
        self.assertEqual(application.text, "a Mercedes Benz sedan")

    def test_cjk_term_matches_without_word_boundaries(self) -> None:
        lexicon = self._lexicon([{"term": "空气动力学", "say": "空气动力学（ke xue）"}])
        application = lexicon_module.apply(lexicon, "汽车空气动力学入门")
        self.assertIn("（ke xue）", application.text)

    def test_no_match_leaves_text_and_hits_empty(self) -> None:
        lexicon = self._lexicon([{"term": "CFD", "say": "C F D"}])
        application = lexicon_module.apply(lexicon, "nothing here")
        self.assertEqual(application.text, "nothing here")
        self.assertFalse(application.changed)

    def test_same_term_with_two_readings_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            self._lexicon(
                [{"term": "A", "say": "ay"}, {"term": "a", "say": "uh"}]
            )


class VoiceBibleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bible_path = self.root / "voice-bibles" / "wayne-en-v1.yaml"
        self.bible_path.parent.mkdir(parents=True)
        self.bible_path.write_text(yaml.safe_dump(BIBLE), encoding="utf-8")
        (self.root / "voice-bibles" / "voice.wav").write_bytes(b"reference")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_relative_ref_audio_resolves_next_to_the_bible(self) -> None:
        bible = voice_bible_module.load(self.bible_path)
        audio = voice_bible_module.ref_audio_path(bible, self.bible_path)
        self.assertEqual(audio, self.root / "voice-bibles" / "voice.wav")
        self.assertEqual(voice_bible_module.check(bible, self.bible_path), [])

    def test_digest_changes_when_the_voice_changes(self) -> None:
        bible = voice_bible_module.load(self.bible_path)
        before = voice_bible_module.digest(bible)
        changed = bible.model_copy(update={"speed": 0.95})
        self.assertNotEqual(before, voice_bible_module.digest(changed))

    def test_declared_hash_mismatch_is_reported(self) -> None:
        payload = dict(BIBLE, ref_audio_sha256="0" * 64)
        self.bible_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        bible = voice_bible_module.load(self.bible_path)
        problems = voice_bible_module.check(bible, self.bible_path)
        self.assertTrue(any("sha256 mismatch" in item for item in problems))

    def test_missing_reference_is_reported(self) -> None:
        payload = dict(BIBLE, ref_audio="gone.wav")
        self.bible_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        bible = voice_bible_module.load(self.bible_path)
        self.assertTrue(any("not found" in item for item in voice_bible_module.check(bible, self.bible_path)))

    def test_prompt_reference_without_prompt_text_is_reported(self) -> None:
        payload = dict(BIBLE, mode="prompt_reference", prompt_text="")
        self.bible_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        bible = voice_bible_module.load(self.bible_path)
        self.assertTrue(
            any("requires prompt_text" in item for item in voice_bible_module.check(bible, self.bible_path))
        )


class ResolveAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: dict) -> None:
        path = self.workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def test_lesson_without_assets_resolves_to_nothing(self) -> None:
        assets = resolve_assets(self.workspace, type("L", (), {"narration": Narration()})())
        self.assertIsNone(assets.voice_bible)
        self.assertIsNone(assets.lexicon)
        self.assertEqual(assets.problems, [])

    def test_declared_assets_are_loaded_and_hashed(self) -> None:
        (self.workspace / "audio" / "voice-bibles").mkdir(parents=True)
        (self.workspace / "audio" / "voice-bibles" / "voice.wav").write_bytes(b"reference")
        self._write("audio/voice-bibles/wayne-en-v1.yaml", BIBLE)
        self._write("audio/lexicons/automotive.yaml", LEXICON)
        lesson = type("L", (), {"narration": Narration(voice_bible="wayne-en-v1", lexicon="automotive")})()

        assets = resolve_assets(self.workspace, lesson)

        self.assertEqual(assets.voice_bible.id, "wayne-en-v1")
        self.assertEqual(assets.lexicon.id, "automotive")
        self.assertEqual(len(assets.voice_bible_sha256), 64)
        self.assertEqual(len(assets.lexicon_sha256), 64)
        self.assertEqual(assets.problems, [])
        self.assertEqual(assets.apply("a CFD case").text, "a C F D case")

    def test_missing_declared_bible_raises(self) -> None:
        lesson = type("L", (), {"narration": Narration(voice_bible="nope")})()
        with self.assertRaises(AudioAssetError):
            resolve_assets(self.workspace, lesson)


class CacheKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ref = Path(self._tmp.name) / "ref.wav"
        self.ref.write_bytes(b"voice")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_legacy_payload_is_unchanged(self) -> None:
        """A lesson with no voice assets must keep producing the old key."""
        expected = sha256_text(
            json.dumps(
                {
                    "text": normalize_stream("Hello world."),
                    "voice_ref": sha256_text(hashlib.sha256(b"voice").hexdigest()),
                    "prompt_text": "prompt",
                    "mode": "reference_only",
                    "style": "calm",
                    "model": "VoxCPM2",
                    "timesteps": 10,
                    "cfg": 2.0,
                    "speed": 0.9,
                    "text_frontend": False,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        actual = segment_cache_key(
            "Hello world.",
            self.ref,
            "prompt",
            mode="reference_only",
            style="calm",
            speed=0.9,
            text_frontend=False,
        )
        self.assertEqual(actual, expected)

    def test_voice_bible_changes_the_key(self) -> None:
        plain = segment_cache_key("Hello.", self.ref, "p")
        with_bible = segment_cache_key("Hello.", self.ref, "p", voice_bible_sha256="a" * 64)
        self.assertNotEqual(plain, with_bible)

    def test_only_segments_using_a_term_get_a_new_key(self) -> None:
        lexicon = lexicon_module.Lexicon.model_validate(LEXICON)
        before = segment_cache_key("nothing here", self.ref, "p")
        untouched = lexicon_module.apply(lexicon, "nothing here")
        after = segment_cache_key(
            untouched.text, self.ref, "p", lexicon_hits=untouched.applied
        )
        self.assertEqual(before, after)

        rewritten = lexicon_module.apply(lexicon, "a CFD case")
        changed = segment_cache_key(
            rewritten.text, self.ref, "p", lexicon_hits=rewritten.applied
        )
        self.assertNotEqual(before, changed)


if __name__ == "__main__":
    unittest.main()
