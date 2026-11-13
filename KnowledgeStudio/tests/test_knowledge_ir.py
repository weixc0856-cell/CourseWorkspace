from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from knowledge_studio.knowledge_ir import (
    Claim,
    Concept,
    Conflict,
    CurriculumPlan,
    EvidenceRef,
    KnowledgeIR,
    LessonSpec,
    deliverable,
    load_curriculum,
    load_knowledge,
    validate_curriculum,
    validate_knowledge,
)


def evidence(source: str, page: int, kind: str = "statement") -> EvidenceRef:
    return EvidenceRef(source_id=source, pdf_page=page, kind=kind)


def knowledge() -> KnowledgeIR:
    return KnowledgeIR(
        concepts=[
            Concept(id="concept.dot-product", label="Dot product"),
            Concept(
                id="concept.self-attention",
                label="Self-attention",
                prerequisites=["concept.dot-product"],
            ),
        ],
        claims=[
            Claim(
                id="claim.attention-scales",
                statement="Attention scales by sqrt(d)",
                concept_ids=["concept.self-attention"],
                evidence=[evidence("book", 315), evidence("paper", 4)],
                verification="supported",
            )
        ],
    )


class KnowledgeValidationTest(unittest.TestCase):
    def test_valid_ir_has_no_errors(self) -> None:
        issues = validate_knowledge(knowledge())
        self.assertFalse([item for item in issues if item.level == "error"])

    def test_unknown_prerequisite_is_an_error(self) -> None:
        ir = knowledge()
        ir.concepts[0].prerequisites.append("concept.missing")
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertIn("concept.unknown_prerequisite", codes)

    def test_cycle_is_detected(self) -> None:
        ir = KnowledgeIR(
            concepts=[
                Concept(id="concept.a", label="A", prerequisites=["concept.b"]),
                Concept(id="concept.b", label="B", prerequisites=["concept.a"]),
            ]
        )
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertIn("concept.cycle", codes)

    def test_supported_needs_two_pages_or_a_derivation(self) -> None:
        ir = knowledge()
        ir.claims[0].evidence = [evidence("book", 315)]
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertIn("claim.insufficient_evidence", codes)

        ir.claims[0].evidence = [evidence("book", 315, kind="derivation")]
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertNotIn("claim.insufficient_evidence", codes)

    def test_contested_needs_a_conflict_and_resolution(self) -> None:
        ir = knowledge()
        ir.claims[0].verification = "contested"
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertIn("claim.contested_without_conflict", codes)

        ir.claims[0].verification = "contested_resolved"
        ir.claims[0].conflicts = [Conflict(source_id="other", pdf_page=9, note="opposite")]
        codes = {item.code for item in validate_knowledge(ir)}
        self.assertIn("claim.resolution_missing", codes)
        self.assertNotIn("claim.contested_without_conflict", codes)

        ir.claims[0].resolution = "book wins: derivation reproduced"
        issues = validate_knowledge(ir)
        self.assertFalse([item for item in issues if item.level == "error"])

    def test_only_supported_or_resolved_claims_are_deliverable(self) -> None:
        ir = knowledge()
        self.assertTrue(deliverable(ir.claims[0]))
        ir.claims[0].verification = "single_source"
        self.assertFalse(deliverable(ir.claims[0]))


class CurriculumValidationTest(unittest.TestCase):
    def plan(self, lessons: list[LessonSpec], exempt: dict | None = None) -> CurriculumPlan:
        return CurriculumPlan(
            project_id="demo",
            lessons=lessons,
            coverage_exempt=exempt or {},
        )

    def test_ordered_curriculum_passes(self) -> None:
        plan = self.plan(
            [
                LessonSpec(id="l1", title="Dot product", concepts=["concept.dot-product"]),
                LessonSpec(id="l2", title="Attention", concepts=["concept.self-attention"]),
            ]
        )
        issues = validate_curriculum(plan, knowledge())
        self.assertFalse([item for item in issues if item.level == "error"])

    def test_prerequisite_taught_later_is_an_error(self) -> None:
        plan = self.plan(
            [
                LessonSpec(id="l1", title="Attention", concepts=["concept.self-attention"]),
                LessonSpec(id="l2", title="Dot product", concepts=["concept.dot-product"]),
            ]
        )
        codes = {item.code for item in validate_curriculum(plan, knowledge())}
        self.assertIn("curriculum.prerequisite_order", codes)

    def test_uncovered_concept_is_an_error_unless_exempt(self) -> None:
        plan = self.plan([LessonSpec(id="l1", title="Dot", concepts=["concept.dot-product"])])
        codes = {item.code for item in validate_curriculum(plan, knowledge())}
        self.assertIn("curriculum.uncovered", codes)

        plan.coverage_exempt = {"concept.self-attention": "covered in a later season"}
        codes = {item.code for item in validate_curriculum(plan, knowledge())}
        self.assertNotIn("curriculum.uncovered", codes)

    def test_lesson_count_window(self) -> None:
        plan = self.plan(
            [
                LessonSpec(id="l1", title="A", concepts=["concept.dot-product"]),
                LessonSpec(id="l2", title="B", concepts=["concept.self-attention"]),
            ]
        )
        codes = {
            item.code
            for item in validate_curriculum(plan, knowledge(), min_lessons=3)
        }
        self.assertIn("curriculum.too_few_lessons", codes)

    def test_files_load_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge_path = root / "knowledge-ir.yaml"
            plan_path = root / "curriculum.yaml"
            knowledge_path.write_text(
                yaml.safe_dump(knowledge().model_dump(mode="json"), sort_keys=False),
                encoding="utf-8",
            )
            plan_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "project_id": "demo",
                        "lessons": [
                            {"id": "l1", "title": "Dot", "concepts": ["concept.dot-product"]},
                            {"id": "l2", "title": "Attention", "concepts": ["concept.self-attention"]},
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(len(load_knowledge(knowledge_path).concepts), 2)
            self.assertEqual(len(load_curriculum(plan_path).lessons), 2)
