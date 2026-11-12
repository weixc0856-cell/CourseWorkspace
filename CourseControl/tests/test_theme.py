from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_control.content.contracts import Shot, ShotSpec
from course_control.rendering.theme import (
    DEFAULT_THEME,
    SCENE_THEMES,
    load_theme,
    theme_names,
    themes_path,
    write_theme_json,
)

WORKSPACE = Path(__file__).resolve().parents[2]
TOKENS = WORKSPACE / "shared" / "design-tokens" / "tokens.json"


class ThemeTokensTest(unittest.TestCase):
    def test_contract_names_match_the_file(self):
        self.assertEqual(set(theme_names(WORKSPACE)), set(SCENE_THEMES))

    def test_default_is_light_and_named(self):
        theme = load_theme(WORKSPACE)
        self.assertEqual(theme["name"], DEFAULT_THEME)
        self.assertTrue(theme["light"])

    def test_editorial_science_matches_the_shared_tokens(self):
        # themes.json must not drift from the tokens every other engine reads
        tokens = json.loads(TOKENS.read_text(encoding="utf-8"))["colors"]
        theme = load_theme(WORKSPACE, "editorial_science")["colors"]
        for key, source in (("paper", "paper"), ("surface", "surface"), ("ink", "ink"),
                            ("body", "text"), ("muted", "muted"), ("border", "border"),
                            ("accent", "orange"), ("blue", "blue"), ("teal", "teal"),
                            ("purple", "purple"), ("red", "red")):
            self.assertEqual(theme[key], tokens[source], key)

    def test_dark_theme_has_light_text_on_dark_ground(self):
        theme = load_theme(WORKSPACE, "deep_space")
        self.assertFalse(theme["light"])
        self.assertEqual(theme["colors"]["paper"], "#0A0908")
        self.assertEqual(theme["colors"]["ink"], "#F4F1EA")

    def test_unknown_theme_raises(self):
        with self.assertRaises(KeyError):
            load_theme(WORKSPACE, "neon")

    def test_write_theme_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "scene" / "theme.json"
            write_theme_json(WORKSPACE, target, "deep_space")
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "deep_space")
            self.assertIn("colors", payload)
            self.assertIn("semantics", payload)

    def test_missing_tokens_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_theme(Path(tmp))


class ThemeContractTest(unittest.TestCase):
    def _shot(self, **overrides):
        payload = dict(
            id="s1", kind="animation", engine="code_video", source="shots/x/SPEC.md",
            start_s=0.0, duration_s=6.0, timeline_role="base",
        )
        payload.update(overrides)
        return Shot(**payload)

    def test_shot_accepts_declared_theme(self):
        self.assertEqual(self._shot(theme="deep_space").theme, "deep_space")

    def test_shot_theme_is_optional(self):
        self.assertIsNone(self._shot().theme)

    def test_shot_rejects_unknown_theme(self):
        with self.assertRaises(ValidationError):
            self._shot(theme="cyberpunk")

    def test_shot_spec_accepts_theme(self):
        spec = ShotSpec(id="s1", slide=1, engine="code_video", scene="shots/x/SPEC.md",
                        cue_seconds=0.0, theme="engineering_studio")
        self.assertEqual(spec.theme, "engineering_studio")


if __name__ == "__main__":
    unittest.main()
