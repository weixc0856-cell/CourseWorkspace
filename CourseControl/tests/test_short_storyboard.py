from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_control.production.short_storyboard import (
    ShortStoryboard,
    load_short,
)

WORKSPACE = Path(__file__).resolve().parents[2]
SAMPLE = WORKSPACE / "RemotionStudio" / "src" / "short" / "sample-base-rate.json"
GALLERY = WORKSPACE / "RemotionStudio" / "src" / "short" / "gallery.json"


def scene(kind: str = "statement", purpose: str = "explain", props: dict | None = None) -> dict:
    return {
        "id": "one",
        "kind": kind,
        "duration_s": 5,
        "purpose": purpose,
        "props": props if props is not None else {"text": "hello"},
    }


def board(scenes: list[dict], **overrides) -> dict:
    payload = {
        "schema_version": 1,
        "id": "fixture",
        "title": "Fixture",
        "theme": "editorial_science",
        "aspect": "16:9",
        "fps": 30,
        "scenes": scenes,
        "captions": [],
    }
    payload.update(overrides)
    return payload


class ShortStoryboardTest(unittest.TestCase):
    def test_sample_and_gallery_load(self):
        sample = load_short(SAMPLE)
        gallery = load_short(GALLERY)
        self.assertEqual(sample.total_seconds, 120.0)
        self.assertEqual(len(sample.scenes), 20)
        self.assertEqual(gallery.total_seconds, 25.0)

    def test_every_scene_declares_a_purpose(self):
        sample = load_short(SAMPLE)
        for item in sample.scenes:
            self.assertIn(
                item.purpose,
                {"explain", "demonstrate", "compare", "orient", "summarize", "emote"},
                item.id,
            )

    def test_missing_purpose_fails(self):
        payload = board([scene()])
        del payload["scenes"][0]["purpose"]
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(payload)

    def test_duplicate_scene_ids_fail(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(board([scene(), scene()]))

    def test_statement_needs_text(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(board([scene(props={})]))

    def test_split_compare_needs_both_sides(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(
                board([scene("split_compare", "compare", {"left": {"title": "A"}})])
            )

    def test_paper_box_must_stay_inside_the_image(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(
                board(
                    [
                        scene(
                            "paper_highlight",
                            "demonstrate",
                            {"image": "x.png", "box": {"x": 0.8, "y": 0.1, "w": 0.4, "h": 0.2}},
                        )
                    ]
                )
            )

    def test_metric_bar_needs_numeric_values(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(
                board([scene("metric_bar", "demonstrate", {"data": [{"label": "A", "value": "25"}]})])
            )

    def test_flow_needs_steps(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(
                board([scene("simple_flow", "explain", {"steps": []})])
            )

    def test_caption_can_carry_spoken_text(self):
        payload = ShortStoryboard.model_validate(
            board(
                [scene()],
                captions=[{"start_s": 0, "end_s": 1, "en": "0.99 x 0.01", "zh": "0.99 乘 0.01", "tts": "0.99 times 0.01"}],
            )
        )
        self.assertEqual(payload.captions[0].tts, "0.99 times 0.01")

    def test_captions_must_be_ordered(self):
        with self.assertRaises(ValidationError):
            ShortStoryboard.model_validate(
                board(
                    [scene()],
                    captions=[
                        {"start_s": 3, "end_s": 5, "en": "late"},
                        {"start_s": 1, "end_s": 2, "en": "early"},
                    ],
                )
            )

    def test_load_reports_a_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(board([{"id": "x"}])), encoding="utf-8")
            with self.assertRaises(Exception):
                load_short(path)


if __name__ == "__main__":
    unittest.main()
