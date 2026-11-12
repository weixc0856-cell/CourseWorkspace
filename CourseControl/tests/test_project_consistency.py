from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

from course_control.direction.animation_direction import AnimationDirection
from course_control.rendering.blender_scene import BlenderSceneTask
from course_control.content.contracts import BuildReport, LessonConfig, ShotsFile, Storyboard
from course_control.content.contracts_v1 import V1_MODELS
from course_control.direction.schema import DirectorPlan
from course_control.rendering.formulas import FormulaSpec
from course_control.rendering.layout.schema import LayoutTemplate
from course_control.delivery.schema import DeliveryManifest, ProductionOrder, ProductionState
from course_control.platform.session import EvidenceManifest, SessionSpec
from course_control.rendering.simulation import SimulationSpec

WORKSPACE = Path(__file__).resolve().parents[2]

SCHEMAS = {
    "lesson": LessonConfig,
    "storyboard": Storyboard,
    "shots": ShotsFile,
    "build-report": BuildReport,
    "blender-scene-task": BlenderSceneTask,
    "session": SessionSpec,
    "evidence": EvidenceManifest,
    "formula": FormulaSpec,
    "animation-direction": AnimationDirection,
    "director-plan": DirectorPlan,
    "production-order": ProductionOrder,
    "production-state": ProductionState,
    "delivery-manifest": DeliveryManifest,
    "layout-template": LayoutTemplate,
    "simulation-spec": SimulationSpec,
    **V1_MODELS,
}


class ProjectConsistencyTest(unittest.TestCase):
    def test_shared_schemas_match_models(self):
        drifted = []
        for name, model in SCHEMAS.items():
            path = WORKSPACE / "shared" / "schemas" / f"{name}.schema.json"
            if not path.is_file():
                drifted.append(f"{name}: missing")
                continue
            if json.loads(path.read_text(encoding="utf-8")) != model.model_json_schema():
                drifted.append(f"{name}: drift")
        self.assertEqual(drifted, [], "regenerate with course-control schemas")

    def test_decision_ids_are_unique(self):
        text = (WORKSPACE / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
        ids = re.findall(r"^## D-(\d+)", text, flags=re.M)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [f"{i:03d}" for i in range(1, len(ids) + 1)])

    def test_prd_fr_ids_are_unique(self):
        text = (WORKSPACE / "docs" / "PRD.md").read_text(encoding="utf-8")
        ids = re.findall(r"^### (FR-\d+)", text, flags=re.M)
        self.assertEqual(len(ids), len(set(ids)))

    def test_claude_index_links_resolve(self):
        text = (WORKSPACE / "CLAUDE.md").read_text(encoding="utf-8")
        broken = []
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("http", "mailto:")):
                continue
            path = WORKSPACE / unquote(target.split("#")[0])
            if not path.exists():
                broken.append(target)
        self.assertEqual(broken, [])

    def test_keyframe_gate_is_gone(self):
        removed_doc = WORKSPACE / "docs" / "评审-向量加法关键帧.md"
        removed_code = WORKSPACE / "ManimSandbox" / "03-vector-intro" / "keyframes.py"
        self.assertFalse(removed_doc.exists())
        self.assertFalse(removed_code.exists())
        for path in [WORKSPACE / "CLAUDE.md", WORKSPACE / "docs" / "TRACEABILITY.md"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("评审-向量加法关键帧", text)


if __name__ == "__main__":
    unittest.main()
