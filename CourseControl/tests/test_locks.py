from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from course_control.locks import LockError, dialogue, diff, affected, picture
from course_control.platform.media import sha256_file
from course_control.content.paths import LessonPaths

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"

SRT = """1
00:00:00,000 --> 00:00:02,000
Hello.

2
00:00:05,000 --> 00:00:07,000
Out of range.
"""


class LockBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson = self.workspace / "lessons" / "lesson-smoke"
        shutil.copytree(FIXTURE, self.lesson)
        self.build = self.workspace / "build" / "lesson-smoke"
        self.build.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _load(self) -> LessonPaths:
        return LessonPaths.load(self.workspace, self.lesson, build_root_override=self.build)

    def _script(self) -> Path:
        path = self.lesson / "authoring" / "narration.script.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema_version": 1, "lesson": "lesson-smoke", "pages": []}),
            encoding="utf-8",
        )
        lesson_yaml = self.lesson / "lesson.yaml"
        text = lesson_yaml.read_text(encoding="utf-8")
        if "authoring:" not in text:
            lesson_yaml.write_text(
                text.rstrip("\n") + "\nauthoring:\n  script: authoring/narration.script.json\n",
                encoding="utf-8",
            )
        return path

    def _narration(self, script: Path, *, recorded: str | None = None) -> None:
        narration = self.build / "narration"
        narration.mkdir(parents=True, exist_ok=True)
        (narration / "narration.wav").write_bytes(b"RIFFfake")
        meta = {
            "schema_version": 3,
            "lesson": "lesson-smoke",
            "duration_s": 7.0,
            "source": {"script_sha256": recorded or sha256_file(script)},
            "assets": {
                "voice_bible": {"id": "wayne-en-v1", "sha256": "a" * 64},
                "lexicon": {"id": "demo", "sha256": "b" * 64},
            },
            "tts": {"model": "VoxCPM2"},
            "segments": [
                {"segment_id": "s001-p1", "slide": 1, "start_s": 0.0, "end_s": 2.0, "duration_s": 2.0},
                {"segment_id": "s002-p1", "slide": 2, "start_s": 2.0, "end_s": 4.0, "duration_s": 2.0},
            ],
        }
        (narration / "narration.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        (self.lesson / "subtitles.srt").write_text(SRT, encoding="utf-8")


class DialogueLockTest(LockBase):
    def test_stale_script_is_reported(self) -> None:
        script = self._script()
        self._narration(script, recorded="0" * 64)
        snap = dialogue.snapshot(self._load())
        check = {item["id"]: item for item in snap["checks"]}["script_matches_narration"]
        self.assertEqual(check["status"], "fail")
        self.assertIn("re-run narration-build", check["detail"])

    def test_matching_script_and_assets_are_recorded(self) -> None:
        script = self._script()
        self._narration(script)
        snap = dialogue.snapshot(self._load())
        checks = {item["id"]: item["status"] for item in snap["checks"]}
        self.assertEqual(checks["script_matches_narration"], "pass")
        self.assertEqual(checks["assets_recorded"], "pass")
        self.assertEqual(snap["hashes"]["voice_bible"], "a" * 64)
        self.assertEqual(snap["hashes"]["lexicon"], "b" * 64)
        self.assertEqual(len(snap["hashes"]["narration"]), 64)

    def test_cues_outside_every_segment_are_reported(self) -> None:
        self._narration(self._script())
        snap = dialogue.snapshot(self._load())
        self.assertEqual(snap["subtitles"]["cues"], 2)
        self.assertEqual(snap["subtitles"]["unmapped"], [2])
        check = {item["id"]: item for item in snap["checks"]}["subtitles_mapped"]
        self.assertEqual(check["status"], "warn")

    def test_missing_narration_is_an_error(self) -> None:
        with self.assertRaises(LockError):
            dialogue.snapshot(self._load())

    def test_write_and_load_roundtrip(self) -> None:
        self._narration(self._script())
        paths = self._load()
        result = dialogue.write(paths, approved_by="wayne", note="listened twice")
        self.assertTrue(result["path"].is_file())
        loaded = dialogue.load(paths)
        self.assertEqual(loaded["review"]["approved_by"], "wayne")
        self.assertEqual(loaded["hashes"], result["lock"]["hashes"])


class PictureLockTest(LockBase):
    def _timeline(self) -> None:
        timeline = self.build / "timeline"
        timeline.mkdir(parents=True, exist_ok=True)
        (timeline / "page-plan.json").write_text(
            json.dumps({"pages": [{"slide": 1, "start_s": 0.0, "duration_s": 4.0}]}),
            encoding="utf-8",
        )
        slides = self.build / "slides"
        slides.mkdir(parents=True, exist_ok=True)
        (slides / "slide-001.png").write_bytes(b"png")

    def test_picture_units_are_hashed(self) -> None:
        self._timeline()
        snap = picture.snapshot(self._load())
        self.assertEqual(len(snap["pictures"]), 1)
        self.assertEqual(snap["pictures"][0]["kind"], "still")
        self.assertEqual(len(snap["hashes"]["picture:page-001"]), 64)
        self.assertIn("sheet:shot_001", snap["hashes"])
        checks = {item["id"]: item["status"] for item in snap["checks"]}
        self.assertEqual(checks["pictures"], "pass")
        self.assertEqual(checks["sheet_version"], "warn")

    def test_changing_a_slide_changes_the_hash(self) -> None:
        self._timeline()
        paths = self._load()
        before = picture.snapshot(paths)["hashes"]["picture:page-001"]
        (self.build / "slides" / "slide-001.png").write_bytes(b"png2")
        after = picture.snapshot(paths)["hashes"]["picture:page-001"]
        self.assertNotEqual(before, after)

    def test_no_timeline_is_an_error(self) -> None:
        with self.assertRaises(LockError):
            picture.snapshot(self._load())


class DependencyRulesTest(unittest.TestCase):
    def test_script_change_names_its_downstream(self) -> None:
        changes = diff({"script": "a"}, {"script": "b"})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change"], "changed")
        self.assertIn("narration", changes[0]["downstream"])
        self.assertIn("subtitles", changes[0]["downstream"])

    def test_namespaced_keys_use_their_base_rule(self) -> None:
        changes = diff({"picture:page-001": "a"}, {"picture:page-001": "b"})
        self.assertEqual(changes[0]["downstream"], ["timeline", "final_compose"])

    def test_added_and_removed_keys_are_reported(self) -> None:
        changes = {item["key"]: item["change"] for item in diff({"a:1": "x"}, {"b:1": "y"})}
        self.assertEqual(changes, {"a:1": "removed", "b:1": "added"})

    def test_affected_dedupes_downstream(self) -> None:
        changes = diff({"picture:a": "1", "picture:b": "2"}, {"picture:a": "x", "picture:b": "y"})
        self.assertEqual(affected(changes), ["timeline", "final_compose"])


if __name__ == "__main__":
    unittest.main()
