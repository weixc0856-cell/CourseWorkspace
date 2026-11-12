from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from course_control.authoring import shot_sheet
from course_control.paths import ContractError, LessonPaths

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"

SHEET = """schema_version: 2
lesson: lesson-smoke

continuity:
  - id: body-shell
    label: 车身外壳
  - id: wake
    label: 尾流

shots:
  - id: shot_001
    slide: 1
    engine: blender
    scene: scenes/lesson-smoke/overlay.blend
    cue_seconds: 1
    purpose: explain
    visual_action: 车身从静止开始加速
    composition: 居中三分之二
    continuity_refs: [body-shell]
    asset_refs: [assets/body.png]
    evidence_refs: [E01-FD-003]
    transition: {in: hard_cut, out: hard_cut}
    director_notes: 先给整体，再切细节
  - id: shot_002
    slide: 2
    engine: blender
    scene: scenes/lesson-smoke/overlay.blend
    cue_seconds: 2
    purpose: demonstrate
    visual_action: 尾流从车尾拖出
    continuity_refs: [body-shell, wake]
"""


class ShotSheetTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson = self.workspace / "lessons" / "lesson-smoke"
        shutil.copytree(FIXTURE, self.lesson)
        (self.lesson / "assets").mkdir(exist_ok=True)
        (self.lesson / "assets" / "body.png").write_bytes(b"png")
        self.build = self.workspace / "build"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_sheet(self, text: str) -> None:
        (self.lesson / "storyboard.yaml").write_text(text, encoding="utf-8")

    def _load(self) -> LessonPaths:
        return LessonPaths.load(self.workspace, self.lesson, build_root_override=self.build)

    def test_v1_storyboard_compiles_without_design_fields(self) -> None:
        plan = shot_sheet.compile_sheet(self._load())
        self.assertEqual(plan["source"]["schema_version"], 1)
        self.assertEqual(plan["summary"]["designed"], 0)
        self.assertEqual(plan["summary"]["continuity_objects"], 0)
        self.assertEqual(plan["issues"], [])

    def test_v2_sheet_resolves_refs_and_continuity(self) -> None:
        self._write_sheet(SHEET)
        plan = shot_sheet.compile_sheet(self._load())

        self.assertEqual(plan["source"]["schema_version"], 2)
        self.assertEqual(plan["summary"]["shots"], 2)
        self.assertEqual(plan["summary"]["designed"], 2)
        self.assertEqual(plan["summary"]["with_assets"], 1)
        self.assertEqual(plan["summary"]["with_evidence"], 1)

        usage = {item["id"]: item["shots"] for item in plan["continuity"]}
        self.assertEqual(usage["body-shell"], ["shot_001", "shot_002"])
        self.assertEqual(usage["wake"], ["shot_002"])
        self.assertEqual(plan["issues"], [])

        first = plan["shots"][0]
        self.assertEqual(first["purpose"], "explain")
        self.assertEqual(first["assets"][0]["found"], True)
        self.assertEqual(len(first["assets"][0]["sha256"]), 64)

    def test_unused_continuity_object_is_reported(self) -> None:
        self._write_sheet(SHEET.replace("continuity_refs: [body-shell, wake]", "continuity_refs: [body-shell]"))
        plan = shot_sheet.compile_sheet(self._load())
        self.assertEqual(plan["summary"]["unused_continuity"], ["wake"])

    def test_fingerprints_are_stable_and_scoped_per_shot(self) -> None:
        self._write_sheet(SHEET)
        first = {shot["id"]: shot["fingerprint"] for shot in shot_sheet.compile_sheet(self._load())["shots"]}
        again = {shot["id"]: shot["fingerprint"] for shot in shot_sheet.compile_sheet(self._load())["shots"]}
        self.assertEqual(first, again)

        self._write_sheet(SHEET.replace("先给整体，再切细节", "先给整体，再切细节，最后回中景"))
        changed = {shot["id"]: shot["fingerprint"] for shot in shot_sheet.compile_sheet(self._load())["shots"]}
        self.assertNotEqual(first["shot_001"], changed["shot_001"])
        self.assertEqual(first["shot_002"], changed["shot_002"])

    def test_missing_asset_is_located(self) -> None:
        self._write_sheet(SHEET.replace("assets/body.png", "assets/gone.png"))
        problems = shot_sheet.issues(self._load())
        self.assertEqual([item["rule"] for item in problems], ["V-46"])
        self.assertIn("assets/gone.png", problems[0]["message"])
        self.assertEqual(problems[0]["shot_id"], "shot_001")

    def test_dangling_continuity_ref_is_located(self) -> None:
        self._write_sheet(SHEET.replace("continuity_refs: [body-shell, wake]", "continuity_refs: [body-shell, ghost]"))
        problems = shot_sheet.issues(self._load())
        self.assertEqual([item["rule"] for item in problems], ["V-45"])
        self.assertEqual(problems[0]["shot_id"], "shot_002")

    def test_malformed_evidence_ref_is_located(self) -> None:
        self._write_sheet(SHEET.replace("[E01-FD-003]", "[E01 FD 003]"))
        problems = shot_sheet.issues(self._load())
        self.assertEqual([item["rule"] for item in problems], ["V-47"])

    def test_sheet_fields_on_a_v1_storyboard_are_rejected(self) -> None:
        self._write_sheet(SHEET.replace("schema_version: 2", "schema_version: 1"))
        with self.assertRaises(ContractError) as caught:
            self._load()
        self.assertIn("schema_version: 2", str(caught.exception))

    def test_write_produces_plan_and_review(self) -> None:
        self._write_sheet(SHEET)
        paths = self._load()
        outputs = shot_sheet.write(paths, shot_sheet.compile_sheet(paths))

        self.assertTrue(outputs["plan"].is_file())
        self.assertTrue(outputs["review"].is_file())
        payload = json.loads(outputs["plan"].read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["shots"], 2)
        review = outputs["review"].read_text(encoding="utf-8")
        self.assertIn("## 连续性", review)
        self.assertIn("`body-shell`", review)


if __name__ == "__main__":
    unittest.main()
