from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.direction.shot_taxonomy import coverage, validate


def taxonomy(status: str = "verified", sample: str | None = "shots/demo") -> dict:
    spec = {
        "status": status,
        "purpose": "p",
        "input_contract": ["a"],
        "visual_goal": "g",
        "use_when": ["u"],
        "avoid_when": ["a"],
        "animation_rules": ["r"],
        "quality_checks": ["q"],
        "sample": sample,
    }
    return {
        "schema_version": 1,
        "types": {
            "concept": dict(spec),
            "mechanism": dict(spec),
            "comparison": dict(spec),
            "data": dict(spec),
            "structure": dict(spec),
            "transformation": dict(spec),
            "narrative": dict(spec),
            "summary": dict(spec),
        },
    }


class ShotTaxonomyTest(unittest.TestCase):
    def test_complete_taxonomy_passes(self) -> None:
        self.assertEqual(validate(taxonomy()), [])

    def test_missing_type_and_field_are_reported(self) -> None:
        data = taxonomy()
        del data["types"]["summary"]
        data["types"]["concept"]["visual_goal"] = ""
        problems = validate(data)
        self.assertTrue(any("missing shot type: summary" in item for item in problems))
        self.assertTrue(any("concept: visual_goal" in item for item in problems))

    def test_verified_requires_a_sample(self) -> None:
        data = taxonomy(sample=None)
        problems = validate(data)
        self.assertTrue(any("verified without a sample" in item for item in problems))

    def test_sample_coverage_requires_spec_and_passing_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            project = workspace / "shots" / "demo"
            project.mkdir(parents=True)
            (project / "SPEC.md").write_text("# spec\n", encoding="utf-8")
            (project / "VERIFY.md").write_text("| must | pass |\n", encoding="utf-8")
            report = coverage(taxonomy(), workspace)
            self.assertEqual(len(report["verified"]), 8)
            (project / "VERIFY.md").write_text("| must | fail |\n", encoding="utf-8")
            report = coverage(taxonomy(), workspace)
            self.assertEqual(report["verified"], [])
            self.assertEqual(len(report["unverified"]), 8)


if __name__ == "__main__":
    unittest.main()
