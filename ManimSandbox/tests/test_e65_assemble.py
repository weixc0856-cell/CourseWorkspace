from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSEMBLE = ROOT / "ManimSandbox" / "05-multi-head" / "assemble.py"
MANIFEST = ROOT / "build" / "manim-multi-head" / "e6.5" / "manifest.json"

spec = importlib.util.spec_from_file_location("e65_assemble", ASSEMBLE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {ASSEMBLE}")
assemble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assemble)


class SrtTest(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(assemble.srt_time(0), "00:00:00,000")
        self.assertEqual(assemble.srt_time(3661.001), "01:01:01,001")
        self.assertEqual(assemble.srt_time(86.929), "00:01:26,929")

    def test_cues_are_ordered_and_long_enough(self):
        self.assertEqual(len(assemble.CUES), 10)
        previous_end = 0.0
        for start, end, text in assemble.CUES:
            self.assertGreater(end, start)
            self.assertGreaterEqual(end - start, 1.5)
            self.assertGreaterEqual(start, previous_end)
            self.assertTrue(text.strip())
            previous_end = end


@unittest.skipUnless(MANIFEST.is_file(), "E6.5 final manifest not present")
class FinalManifestTest(unittest.TestCase):
    def test_final_manifest_passes_checks(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(payload["all_ok"])
        self.assertEqual(payload["subtitles"]["cues"], 10)
        self.assertEqual(payload["video"]["duration_s"], 86.929)
        self.assertTrue(all(item["status"] == "pass" for item in payload["checks"].values()))
        self.assertTrue((ROOT / payload["video"]["file"]).is_file())


if __name__ == "__main__":
    unittest.main()
