"""Book figures must stay locked to their Docling export.

Three failures motivated these checks: a processed image stored as pristine,
a delivered figure silently edited, and page numbers mixing PDF pages with
printed pages.  Each rule has a negative case that must turn red.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml
from PIL import Image

from course_control.production.preflight import evidence_problems


class EvidenceLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.workspace = self.tmp / "ws"
        (self.workspace / "config").mkdir(parents=True)
        (self.workspace / "config" / "local-paths.yaml").write_text(
            f"docling_root: {self.tmp / 'docling'}\n", encoding="utf-8"
        )
        self.bundle = self.tmp / "docling" / "output" / "hucho-en-5e"
        (self.bundle / "assets").mkdir(parents=True)
        (self.bundle / "document.md").write_text(
            "<!-- ks:page pdf=23 -->\n![Image](assets/image_test.png)\n",
            encoding="utf-8",
        )

        self.lesson = self.tmp / "lesson"
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "assets" / "fig" / "pristine").mkdir(parents=True)
        self.pristine = self.lesson / "assets" / "fig" / "pristine" / "fig-1.png"
        self.delivered = self.lesson / "assets" / "fig" / "fig-1.png"
        Image.new("RGB", (20, 10), (200, 30, 30)).save(self.pristine)
        shutil.copyfile(self.pristine, self.delivered)
        self.asset = self.bundle / "assets" / "image_test.png"
        shutil.copyfile(self.pristine, self.asset)
        self.slides = self.lesson / "slides.md"
        self.slides.write_text(
            '<div class="src">printed p. 2 (PDF p. 23)</div>\n', encoding="utf-8"
        )
        self.manifest = {
            "page_offsets": {"hucho-en-5e": 21},
            "figures": [
                {
                    "figure_id": "Fig. 1",
                    "source_edition": "hucho-en-5e",
                    "file_path": "assets/fig/fig-1.png",
                    "pristine_path": "assets/fig/pristine/fig-1.png",
                    "docling_asset": "hucho-en-5e/assets/image_test.png",
                    "pixel_policy": "exact",
                    "printed_page": 2,
                    "pdf_page": 23,
                }
            ],
        }
        self.write_manifest()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_manifest(self, manifest: dict | None = None) -> None:
        path = self.lesson / "authoring" / "evidence.manifest.yaml"
        path.write_text(yaml.safe_dump(manifest or self.manifest), encoding="utf-8")

    def check(self, spec=None) -> tuple[list[str], list[str]]:
        return evidence_problems(self.lesson, self.workspace, spec)

    def test_clean_manifest_passes(self) -> None:
        errors, _ = self.check()
        self.assertEqual([], errors)

    def test_pristine_must_be_the_docling_export(self) -> None:
        Image.new("RGB", (20, 10), (0, 0, 0)).save(self.pristine)
        errors, _ = self.check()
        self.assertTrue(any("pristine is not byte-identical" in e for e in errors), errors)

    def test_exact_figure_must_match_pristine(self) -> None:
        Image.new("RGB", (20, 10), (0, 0, 0)).save(self.delivered)
        errors, _ = self.check()
        self.assertTrue(any("delivered image differs from pristine" in e for e in errors), errors)

    def test_crop_must_be_lossless(self) -> None:
        self.manifest["figures"][0]["pixel_policy"] = "crop"
        self.manifest["figures"][0]["crop_box"] = [2, 2, 12, 8]
        with Image.open(self.pristine) as handle:
            handle.crop((2, 2, 12, 8)).save(self.delivered)
        self.write_manifest()
        errors, _ = self.check()
        self.assertEqual([], errors)
        edited = Image.open(self.delivered).convert("RGB")
        edited.putpixel((0, 0), (0, 0, 0))
        edited.save(self.delivered)
        errors, _ = self.check()
        self.assertTrue(any("lossless crop" in e for e in errors), errors)

    def test_page_offset_must_be_constant(self) -> None:
        second = dict(self.manifest["figures"][0])
        second["figure_id"] = "Fig. 2"
        second["printed_page"] = 2
        second["pdf_page"] = 24  # 22, not the declared 21
        self.manifest["figures"].append(second)
        self.write_manifest()
        errors, _ = self.check()
        self.assertTrue(any("mixed page convention" in e for e in errors), errors)

    def test_pdf_page_must_match_docling(self) -> None:
        self.manifest["figures"][0]["printed_page"] = 3
        self.manifest["figures"][0]["pdf_page"] = 24  # offset 21, but Docling says 23
        self.write_manifest()
        errors, _ = self.check()
        self.assertTrue(any("does not match the Docling page 23" in e for e in errors), errors)

    def test_slides_pair_must_use_a_known_offset(self) -> None:
        self.slides.write_text(
            '<div class="src">printed p. 50 (PDF p. 72)</div>\n', encoding="utf-8"
        )
        errors, _ = self.check()
        self.assertTrue(any("slides.md:1" in e for e in errors), errors)

    def test_missing_manifest_blocks_book_assets(self) -> None:
        (self.lesson / "authoring" / "evidence.manifest.yaml").unlink()
        spec = SimpleNamespace(assets=[{"role": "book_figure"}])
        errors, _ = self.check(spec)
        self.assertTrue(any("evidence.manifest.yaml is missing" in e for e in errors), errors)

    def test_missing_manifest_is_fine_without_book_assets(self) -> None:
        (self.lesson / "authoring" / "evidence.manifest.yaml").unlink()
        spec = SimpleNamespace(assets=[{"role": "render_only"}])
        errors, _ = self.check(spec)
        self.assertEqual([], errors)

    def test_chapter_specific_offset(self) -> None:
        self.manifest["page_offsets"] = {"hucho-en-5e": {"1": 21}}
        self.manifest["figures"][0]["section"] = "§1.2"
        self.write_manifest()
        errors, _ = self.check()
        self.assertEqual([], errors)
        self.manifest["figures"][0]["section"] = "§4.1"
        self.write_manifest()
        errors, _ = self.check()
        self.assertTrue(
            any("no page offset declared for chapter '4'" in e for e in errors), errors
        )

    def test_slash_page_pair_is_checked(self) -> None:
        self.slides.write_text(
            '<div class="src">Printed p. 5 / PDF p. 27</div>\n', encoding="utf-8"
        )
        errors, _ = self.check()
        self.assertTrue(any("slides.md:1" in e for e in errors), errors)
