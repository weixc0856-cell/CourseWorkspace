"""Knowledge IR and curriculum validation.

The page-addressed evidence model answers "where does this sentence come from".
This layer answers two questions the production line needs before authoring:

* what the system understands (concepts, prerequisites, claims, evidence);
* how a course is organised (which lesson teaches which concept, in what order).

Validation is deterministic.  It never decides that a claim is true; it decides
whether the recorded evidence is sufficient to carry the claim into a course.
Tools never upgrade a claim to ``supported`` on their own.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from .models import StrictModel

ConceptId = str
ClaimId = str

CONCEPT_ID = r"^concept\.[a-z0-9][a-z0-9_.-]{0,63}$"
CLAIM_ID = r"^claim\.[a-z0-9][a-z0-9_.-]{0,63}$"

Verification = Literal[
    "unsupported",
    "single_source",
    "supported",
    "contested",
    "contested_resolved",
    "refuted",
    "unverifiable",
]


class EvidenceRef(StrictModel):
    source_id: str = Field(min_length=1)
    pdf_page: int = Field(ge=1)
    printed_page: int | None = None
    kind: Literal["statement", "derivation", "data", "figure"] = "statement"
    quote: str | None = None


class Conflict(StrictModel):
    source_id: str = Field(min_length=1)
    pdf_page: int = Field(ge=1)
    note: str = Field(min_length=1)


class Concept(StrictModel):
    id: ConceptId = Field(pattern=CONCEPT_ID)
    label: str = Field(min_length=1)
    kind: Literal[
        "definition", "mechanism", "quantity", "method", "example", "other"
    ] = "other"
    prerequisites: list[ConceptId] = []
    units: list[str] = []
    citations: list[EvidenceRef] = []


class Claim(StrictModel):
    id: ClaimId = Field(pattern=CLAIM_ID)
    statement: str = Field(min_length=1)
    type: Literal[
        "definition", "quantitative", "causal", "comparative", "procedural", "other"
    ] = "other"
    concept_ids: list[ConceptId] = []
    evidence: list[EvidenceRef] = []
    verification: Verification = "unsupported"
    conflicts: list[Conflict] = []
    resolution: str | None = None


class KnowledgeIR(StrictModel):
    schema_version: Literal[1] = 1
    source_ids: list[str] = []
    concepts: list[Concept] = []
    claims: list[Claim] = []


class LessonSpec(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    concepts: list[ConceptId] = []
    assumes_known: list[ConceptId] = []


class CurriculumPlan(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1)
    lessons: list[LessonSpec] = []
    # concept id -> why it is deliberately not taught in this course
    coverage_exempt: dict[str, str] = {}


class Issue(StrictModel):
    code: str
    level: Literal["error", "warning"]
    message: str


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def _concept_cycle(concepts: list[Concept]) -> list[str] | None:
    graph = {item.id: list(item.prerequisites) for item in concepts}
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> list[str] | None:
        mark = state.get(node, 0)
        if mark == 1:
            return path[path.index(node) :] + [node]
        if mark == 2:
            return None
        state[node] = 1
        for dependency in graph.get(node, []):
            if dependency in graph:
                cycle = visit(dependency, path + [node])
                if cycle:
                    return cycle
        state[node] = 2
        return None

    for concept in concepts:
        cycle = visit(concept.id, [])
        if cycle:
            return cycle
    return None


def validate_knowledge(ir: KnowledgeIR) -> list[Issue]:
    issues: list[Issue] = []
    concept_ids = {item.id for item in ir.concepts}
    claim_ids = {item.id for item in ir.claims}

    for duplicate in _duplicates([item.id for item in ir.concepts]):
        issues.append(Issue(code="concept.duplicate", level="error", message=duplicate))
    for duplicate in _duplicates([item.id for item in ir.claims]):
        issues.append(Issue(code="claim.duplicate", level="error", message=duplicate))

    for concept in ir.concepts:
        for prerequisite in concept.prerequisites:
            if prerequisite not in concept_ids:
                issues.append(
                    Issue(
                        code="concept.unknown_prerequisite",
                        level="error",
                        message=f"{concept.id} requires unknown {prerequisite}",
                    )
                )

    cycle = _concept_cycle(ir.concepts)
    if cycle:
        issues.append(
            Issue(
                code="concept.cycle",
                level="error",
                message=" -> ".join(cycle),
            )
        )

    for claim in ir.claims:
        for concept_id in claim.concept_ids:
            if concept_id not in concept_ids:
                issues.append(
                    Issue(
                        code="claim.unknown_concept",
                        level="error",
                        message=f"{claim.id} references unknown {concept_id}",
                    )
                )
        if claim.verification in {"supported", "single_source"} and not claim.evidence:
            issues.append(
                Issue(
                    code="claim.missing_evidence",
                    level="error",
                    message=f"{claim.id} is {claim.verification} without evidence",
                )
            )
        elif not claim.evidence:
            issues.append(
                Issue(
                    code="claim.no_evidence",
                    level="warning",
                    message=f"{claim.id} has no evidence yet",
                )
            )
        if claim.verification == "supported":
            independent = {(item.source_id, item.pdf_page) for item in claim.evidence}
            derivation = any(item.kind == "derivation" for item in claim.evidence)
            if len(independent) < 2 and not derivation:
                issues.append(
                    Issue(
                        code="claim.insufficient_evidence",
                        level="error",
                        message=(
                            f"{claim.id} needs two independent pages or a derivation, "
                            f"has {len(independent)}"
                        ),
                    )
                )
        if claim.verification in {"contested", "contested_resolved"} and not claim.conflicts:
            issues.append(
                Issue(
                    code="claim.contested_without_conflict",
                    level="error",
                    message=f"{claim.id} is contested but records no conflicting source",
                )
            )
        if claim.verification == "contested_resolved" and not (claim.resolution or "").strip():
            issues.append(
                Issue(
                    code="claim.resolution_missing",
                    level="error",
                    message=f"{claim.id} is contested_resolved without a resolution",
                )
            )
    return issues


def deliverable(claim: Claim) -> bool:
    return claim.verification in {"supported", "contested_resolved"}


def validate_curriculum(
    plan: CurriculumPlan,
    ir: KnowledgeIR,
    *,
    min_lessons: int | None = None,
    max_lessons: int | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    concept_ids = {item.id for item in ir.concepts}

    for duplicate in _duplicates([item.id for item in plan.lessons]):
        issues.append(Issue(code="lesson.duplicate", level="error", message=duplicate))

    if min_lessons is not None and len(plan.lessons) < min_lessons:
        issues.append(
            Issue(
                code="curriculum.too_few_lessons",
                level="error",
                message=f"{len(plan.lessons)} < min {min_lessons}",
            )
        )
    if max_lessons is not None and len(plan.lessons) > max_lessons:
        issues.append(
            Issue(
                code="curriculum.too_many_lessons",
                level="error",
                message=f"{len(plan.lessons)} > max {max_lessons}",
            )
        )

    first_lesson: dict[str, int] = {}
    assumed_globally: set[str] = set()
    for index, lesson in enumerate(plan.lessons):
        for concept_id in lesson.concepts:
            if concept_id not in concept_ids:
                issues.append(
                    Issue(
                        code="lesson.unknown_concept",
                        level="error",
                        message=f"{lesson.id} teaches unknown {concept_id}",
                    )
                )
            else:
                first_lesson.setdefault(concept_id, index)
        for concept_id in lesson.assumes_known:
            if concept_id not in concept_ids:
                issues.append(
                    Issue(
                        code="lesson.unknown_assumption",
                        level="error",
                        message=f"{lesson.id} assumes unknown {concept_id}",
                    )
                )
            assumed_globally.add(concept_id)

    for concept in ir.concepts:
        if concept.id not in first_lesson and concept.id not in plan.coverage_exempt:
            issues.append(
                Issue(
                    code="curriculum.uncovered",
                    level="error",
                    message=f"{concept.id} is not taught by any lesson",
                )
            )
    for concept_id, reason in plan.coverage_exempt.items():
        if concept_id not in concept_ids:
            issues.append(
                Issue(
                    code="curriculum.exempt_unknown",
                    level="error",
                    message=f"exempt concept not in knowledge: {concept_id}",
                )
            )
        if not (reason or "").strip():
            issues.append(
                Issue(
                    code="curriculum.exempt_without_reason",
                    level="error",
                    message=f"exempt concept has no reason: {concept_id}",
                )
            )

    by_id = {item.id: item for item in ir.concepts}
    for index, lesson in enumerate(plan.lessons):
        for concept_id in lesson.concepts:
            concept = by_id.get(concept_id)
            if concept is None:
                continue
            for prerequisite in concept.prerequisites:
                if prerequisite in assumed_globally:
                    continue
                introduced = first_lesson.get(prerequisite)
                if introduced is None:
                    issues.append(
                        Issue(
                            code="curriculum.prerequisite_uncovered",
                            level="error",
                            message=f"{concept.id} needs {prerequisite}, which no lesson teaches",
                        )
                    )
                elif introduced >= index:
                    issues.append(
                        Issue(
                            code="curriculum.prerequisite_order",
                            level="error",
                            message=(
                                f"{concept.id} is taught in {lesson.id} before "
                                f"{prerequisite}"
                            ),
                        )
                    )
    return issues


def load_knowledge(path: Path) -> KnowledgeIR:
    data = yaml_safe(path)
    return KnowledgeIR.model_validate(data)


def load_curriculum(path: Path) -> CurriculumPlan:
    data = yaml_safe(path)
    return CurriculumPlan.model_validate(data)


def yaml_safe(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected a mapping: {path}")
    return data


def write_json(model, path: Path) -> Path:
    payload = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


__all__ = [
    "EvidenceRef",
    "Conflict",
    "Concept",
    "Claim",
    "KnowledgeIR",
    "LessonSpec",
    "CurriculumPlan",
    "Issue",
    "validate_knowledge",
    "validate_curriculum",
    "deliverable",
    "load_knowledge",
    "load_curriculum",
    "write_json",
]
