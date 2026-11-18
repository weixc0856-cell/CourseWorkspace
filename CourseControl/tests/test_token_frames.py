from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from course_control.rendering.token_frames import (
    TokenFrameError,
    cells,
    compare_frames,
    load_layout,
    load_tokens,
)

WORKSPACE = Path(__file__).resolve().parents[2]
LAYOUT = WORKSPACE / "shared" / "design-tokens" / "swatch-layout.json"
TOKENS = WORKSPACE / "shared" / "design-tokens" / "tokens.json"

COLORS = {
    "paper": (251, 250, 247),
    "surface": (243, 241, 234),
    "ink": (37, 42, 49),
    "text": (46, 51, 56),
    "muted": (107, 114, 128),
    "border": (227, 224, 215),
    "orange": (232, 115, 59),
    "blue": (74, 130, 184),
    "teal": (66, 166, 154),
    "purple": (122, 111, 176),
    "red": (199, 91, 85),
    "navy": (18, 50, 74),
    "flow": (168, 198, 222),
}


def draw(
    path: Path,
    layout: dict,
    *,
    override: str | None = None,
    color: tuple[int, int, int] | None = None,
    omit: str | None = None,
) -> None:
    image = Image.new("RGB", (layout["width"], layout["height"]), COLORS["paper"])
    drawer = ImageDraw.Draw(image)
    for cell in cells(layout):
        if cell["key"] == omit:
            continue
        fill = COLORS[cell["key"]]
        if cell["key"] == override and color is not None:
            fill = color
        drawer.rectangle(
            [cell["x"], cell["y"], cell["x"] + cell["w"] - 1, cell["y"] + cell["h"] - 1],
            fill=fill,
        )
    image.save(path)


class TokenFrameTest(unittest.TestCase):
    def setUp(self):
        self.layout = load_layout(LAYOUT)
        self.tokens = load_tokens(TOKENS)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_frames_pass(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout)
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "PASS", report["failed"])
        self.assertEqual(report["worst"]["max"], 0)
        self.assertEqual(report["schema_version"], 2)
        self.assertIsNotNone(report["frame_a_sha256"])

    def test_one_drifted_cell_fails(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout, override="orange", color=(0, 0, 0))
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("orange", report["failed"])

    def test_two_blank_frames_fail(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        Image.new("RGB", (1920, 1080), COLORS["paper"]).save(first)
        Image.new("RGB", (1920, 1080), COLORS["paper"]).save(second)
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("ink", report["failed"])

    def test_both_frames_missing_the_same_cell_fail(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout, omit="orange")
        draw(second, self.layout, omit="orange")
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("orange", report["failed"])

    def test_both_frames_wrong_in_the_same_way_fail(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout, override="orange", color=(0, 0, 0))
        draw(second, self.layout, override="orange", color=(0, 0, 0))
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("orange", report["failed"])

    def test_hashes_are_recorded_when_paths_are_given(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout)
        report = compare_frames(
            first,
            second,
            self.layout,
            self.tokens,
            layout_path=LAYOUT,
            tokens_path=TOKENS,
        )
        self.assertEqual(len(report["layout_sha256"]), 64)
        self.assertEqual(len(report["tokens_sha256"]), 64)

    def test_wrong_size_is_an_error(self):
        first = self.root / "a.png"
        Image.new("RGB", (640, 360), (0, 0, 0)).save(first)
        second = self.root / "b.png"
        draw(second, self.layout)
        with self.assertRaises(TokenFrameError):
            compare_frames(first, second, self.layout, self.tokens)

    def test_missing_frame_is_an_error(self):
        with self.assertRaises(TokenFrameError):
            compare_frames(
                self.root / "missing.png", self.root / "x.png", self.layout, self.tokens
            )

    def test_layout_cells_cover_every_key(self):
        cells_ = cells(self.layout)
        self.assertEqual([cell["key"] for cell in cells_], self.layout["keys"])
        self.assertTrue(all(cell["x"] >= 0 and cell["y"] >= 0 for cell in cells_))

    def _bad_layout(self, **changes) -> dict:
        payload = json.loads(json.dumps(self.layout))
        for key, value in changes.items():
            if key.startswith("cell_"):
                payload["cell"][key.removeprefix("cell_")] = value
            elif key.startswith("origin_"):
                payload["origin"][key.removeprefix("origin_")] = value
            else:
                payload[key] = value
        return payload

    def _layout_file(self, payload: dict) -> Path:
        path = self.root / "layout.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_zero_columns_is_rejected(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(columns=0)))

    def test_zero_cell_is_rejected(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(cell_w=0)))

    def test_negative_origin_is_rejected(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(origin_x=-1)))

    def test_cell_outside_canvas_is_rejected(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(origin_x=1800)))

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(keys=["ink", "ink"])))

    def test_paper_cannot_be_a_swatch(self):
        with self.assertRaises(TokenFrameError):
            load_layout(self._layout_file(self._bad_layout(keys=["paper", "ink"])))

    def test_wrong_background_in_both_frames_fails(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout)
        for path in (first, second):
            image = Image.open(path).convert("RGB")
            drawer = ImageDraw.Draw(image)
            drawer.rectangle([0, 0, 40, 40], fill=(0, 0, 0))
            image.save(path)
        report = compare_frames(first, second, self.layout, self.tokens)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("background", report["failed"])

    def test_missing_key_is_reported(self):
        path = self.root / "layout.json"
        path.write_text(json.dumps({"width": 1920}), encoding="utf-8")
        with self.assertRaises(TokenFrameError):
            load_layout(path)

    def test_bad_token_hex_is_rejected(self):
        path = self.root / "tokens.json"
        path.write_text(json.dumps({"colors": {"paper": "not-a-colour"}}), encoding="utf-8")
        with self.assertRaises(TokenFrameError):
            load_tokens(path)

    def test_layout_key_missing_from_tokens_is_rejected(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout)
        tokens = dict(self.tokens)
        tokens.pop("flow")
        with self.assertRaises(TokenFrameError):
            compare_frames(first, second, self.layout, tokens)




class BrandEvidenceTest(unittest.TestCase):
    def setUp(self):
        import shutil
        from types import SimpleNamespace

        self.SimpleNamespace = SimpleNamespace
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "workspace"
        tokens_dir = self.workspace / "shared" / "design-tokens"
        tokens_dir.mkdir(parents=True)
        shutil.copy2(LAYOUT, tokens_dir / "swatch-layout.json")
        shutil.copy2(TOKENS, tokens_dir / "tokens.json")
        self.layout = load_layout(tokens_dir / "swatch-layout.json")
        self.tokens = load_tokens(tokens_dir / "tokens.json")
        self.build = self.root / "build"
        self.report_path = self.build / "brand" / "token-frames" / "report.json"
        self.report_path.parent.mkdir(parents=True)
        self.frame_a = self.root / "a.png"
        self.frame_b = self.root / "b.png"
        draw(self.frame_a, self.layout)
        draw(self.frame_b, self.layout)

    def tearDown(self):
        self.tmp.cleanup()

    def _paths(self, enabled: bool = True):
        return self.SimpleNamespace(
            lesson=self.SimpleNamespace(branding=self.SimpleNamespace(enabled=enabled)),
            build_root=self.build,
            workspace=self.workspace,
        )

    def _report(self) -> dict:
        return compare_frames(
            self.frame_a,
            self.frame_b,
            self.layout,
            self.tokens,
            layout_path=self.workspace / "shared" / "design-tokens" / "swatch-layout.json",
            tokens_path=self.workspace / "shared" / "design-tokens" / "tokens.json",
        )

    def _write(self, report) -> None:
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

    def _step(self):
        from course_control.release.check import _brand_steps

        return _brand_steps(self._paths(True))[0]

    def test_unbranded_lesson_has_no_step(self):
        from course_control.release.check import _brand_steps

        self.assertEqual(_brand_steps(self._paths(False)), [])

    def test_branded_lesson_without_evidence_is_incomplete(self):
        from course_control.release.check import INCOMPLETE

        self.assertEqual(self._step().status, INCOMPLETE)

    def test_complete_evidence_passes(self):
        from course_control.release.check import PASS

        self._write(self._report())
        self.assertEqual(self._step().status, PASS)

    def test_stub_report_is_incomplete(self):
        from course_control.release.check import INCOMPLETE
        from course_control.rendering.token_frames import file_sha256

        layout = self.workspace / "shared" / "design-tokens" / "swatch-layout.json"
        tokens = self.workspace / "shared" / "design-tokens" / "tokens.json"
        self._write(
            {
                "status": "PASS",
                "layout_sha256": file_sha256(layout),
                "tokens_sha256": file_sha256(tokens),
            }
        )
        self.assertEqual(self._step().status, INCOMPLETE)

    def test_non_object_report_is_incomplete(self):
        from course_control.release.check import INCOMPLETE

        self._write([])
        self.assertEqual(self._step().status, INCOMPLETE)

    def test_missing_row_is_incomplete(self):
        from course_control.release.check import INCOMPLETE

        report = self._report()
        report["rows"].pop()
        self._write(report)
        self.assertEqual(self._step().status, INCOMPLETE)

    def test_frame_hash_mismatch_fails(self):
        from course_control.release.check import FAIL

        report = self._report()
        report["frame_a_sha256"] = "0" * 64
        self._write(report)
        self.assertEqual(self._step().status, FAIL)

    def test_row_over_tolerance_fails(self):
        from course_control.release.check import FAIL

        report = self._report()
        row = report["rows"][1]
        row["a"] = [0, 0, 0]
        row["max"] = max(
            max(abs(row["a"][i] - row["b"][i]) for i in range(3)),
            max(abs(row["a"][i] - row["expected"][i]) for i in range(3)),
            max(abs(row["b"][i] - row["expected"][i]) for i in range(3)),
        )
        self._write(report)
        self.assertEqual(self._step().status, FAIL)

    def test_stale_input_hash_fails(self):
        from course_control.release.check import FAIL

        report = self._report()
        report["layout_sha256"] = "0" * 64
        self._write(report)
        self.assertEqual(self._step().status, FAIL)

    def test_forged_rows_with_real_hashes_fail(self):
        from course_control.release.check import FAIL

        report = self._report()
        for row in report["rows"]:
            row["expected"] = [0, 0, 0]
            row["a"] = [0, 0, 0]
            row["b"] = [0, 0, 0]
            row["max"] = 0
        self._write(report)
        self.assertEqual(self._step().status, FAIL)

    def test_widened_tolerance_fails(self):
        from course_control.release.check import FAIL

        report = self._report()
        report["tolerance"] = 255
        self._write(report)
        self.assertEqual(self._step().status, FAIL)

    def test_forged_pass_with_blank_frames_fails(self):
        from course_control.release.check import FAIL

        Image.new("RGB", (1920, 1080), COLORS["paper"]).save(self.frame_a)
        Image.new("RGB", (1920, 1080), COLORS["paper"]).save(self.frame_b)
        report = self._report()
        self.assertEqual(report["status"], "FAIL")
        report["status"] = "PASS"
        self._write(report)
        self.assertEqual(self._step().status, FAIL)


if __name__ == "__main__":
    unittest.main()
