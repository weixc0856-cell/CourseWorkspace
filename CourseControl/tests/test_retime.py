from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.production.retime import RetimeError, compute, load_narration, render_markdown, write_retime

SEGMENTS = {
    "s1": {"segment_id": "s1", "start_s": 0.0, "end_s": 10.0},
    "s2": {"segment_id": "s2", "start_s": 10.0, "end_s": 25.0},
    "s3": {"segment_id": "s3", "start_s": 25.0, "end_s": 40.0},
}


def mapping(**overrides):
    data = {
        "schema_version": 1,
        "source": "test-track",
        "beats": [
            {"id": "B1", "type": "question", "claims": ["C01"], "segments": ["s1"]},
            {"id": "B2", "type": "case", "claims": ["C02"], "segments": ["s2", "s3"]},
        ],
    }
    data.update(overrides)
    return data


class RetimeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _meta(self):
        path = self.root / "build" / "narration" / "narration.meta.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"segments": list(SEGMENTS.values())}), encoding="utf-8")
        return path

    def _map(self, data):
        path = self.root / "beat-segments.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def test_measured_durations(self):
        timings = compute(SEGMENTS, mapping())
        self.assertEqual([item.seconds for item in timings], [10.0, 30.0])

    def test_markdown_marks_the_source(self):
        text = render_markdown(compute(SEGMENTS, mapping()), "test-track")
        self.assertIn("measured(test-track)", text)
        self.assertIn("| B2 | case | 30.0 |", text)

    def test_unassigned_segment_fails(self):
        data = mapping()
        data["beats"][1]["segments"] = ["s2"]
        with self.assertRaises(RetimeError):
            compute(SEGMENTS, data)

    def test_unknown_segment_fails(self):
        data = mapping()
        data["beats"][0]["segments"] = ["s404"]
        with self.assertRaises(RetimeError):
            compute(SEGMENTS, data)

    def test_duplicate_segment_fails(self):
        data = mapping()
        data["beats"][1]["segments"] = ["s1", "s2", "s3"]
        with self.assertRaises(RetimeError):
            compute(SEGMENTS, data)

    def test_empty_beat_fails(self):
        data = mapping()
        data["beats"][0]["segments"] = []
        with self.assertRaises(RetimeError):
            compute(SEGMENTS, data)

    def test_write_retime_outputs_both_files(self):
        lesson = self.root / "lesson"
        (lesson / "authoring").mkdir(parents=True)
        meta = self._meta()
        write_retime(lesson, self.root / "build", self._map(mapping()), meta)
        self.assertTrue((lesson / "authoring" / "beat-timing.md").is_file())
        self.assertTrue((self.root / "build" / "retime" / "beat-timing.json").is_file())


if __name__ == "__main__":
    unittest.main()
