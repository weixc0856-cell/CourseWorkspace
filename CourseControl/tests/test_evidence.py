from __future__ import annotations

import unittest

from course_control.quality.evidence import (
    approval_problems,
    is_named_approver,
    normalize_dimensions,
    quality_content_sha256,
)

HASHES = {
    "build_report_sha256": "a" * 64,
    "final_video_sha256": "b" * 64,
    "quality_content_sha256": "c" * 64,
}


def report(*statuses: str, **overrides) -> dict:
    ids = ("Q1", "Q2", "Q3", "Q4", "Q5")
    return {
        "dimensions": [
            {"id": qid, "status": status} for qid, status in zip(ids, statuses)
        ],
        **overrides,
    }


def approval(slot: str, **overrides) -> dict:
    data = {
        "schema_version": 2,
        "lesson": "demo",
        "stage": slot,
        "decision": "approved",
        "approved_by": "Wei Chen",
        "build_report_sha256": HASHES["build_report_sha256"],
        "final_video_sha256": HASHES["final_video_sha256"],
        "quality_report_content_sha256": HASHES["quality_content_sha256"],
    }
    data.update(overrides)
    return data


class EvidenceTest(unittest.TestCase):
    def test_unknown_status_is_incomplete(self) -> None:
        statuses, problems = normalize_dimensions(report(*(["banana"] * 5)))
        self.assertEqual(set(statuses.values()), {"INCOMPLETE"})
        self.assertTrue(any("not one of" in item for item in problems), problems)

    def test_duplicate_dimension_is_incomplete(self) -> None:
        data = report("PASS", "PASS", "PASS", "PASS", "PASS")
        data["dimensions"].append({"id": "Q4", "status": "PASS"})
        statuses, problems = normalize_dimensions(data)
        self.assertEqual(statuses["Q4"], "PASS")
        self.assertTrue(any("more than once" in item for item in problems), problems)

    def test_missing_dimension_is_incomplete(self) -> None:
        data = report("PASS", "PASS", "PASS", "PASS", "PASS")
        data["dimensions"] = data["dimensions"][:4]
        statuses, problems = normalize_dimensions(data)
        self.assertEqual(statuses["Q5"], "INCOMPLETE")
        self.assertTrue(any("Q5 is missing" in item for item in problems), problems)

    def test_Q5_reason_does_not_change_the_content_hash(self) -> None:
        first = report("PASS", "PASS", "PASS", "PASS", "PASS")
        first["dimensions"][4]["reason"] = "human review approval is pending"
        second = report("PASS", "PASS", "PASS", "PASS", "PASS")
        second["dimensions"][4]["reason"] = "release sign-off is pending"
        self.assertEqual(quality_content_sha256(first), quality_content_sha256(second))

    def test_Q1_reason_changes_the_content_hash(self) -> None:
        first = report("WARN", "PASS", "PASS", "PASS", "PASS")
        first["dimensions"][0]["reason"] = "one finding"
        second = report("WARN", "PASS", "PASS", "PASS", "PASS")
        second["dimensions"][0]["reason"] = "two findings"
        self.assertNotEqual(
            quality_content_sha256(first), quality_content_sha256(second)
        )

    def test_machine_names_are_not_approvers(self) -> None:
        for value in ("human", "owner", "claude", "system", "unassigned", "", None):
            self.assertFalse(is_named_approver(value), value)
        self.assertTrue(is_named_approver("Wei Chen"))

    def test_approval_must_match_lesson_and_stage(self) -> None:
        problems = approval_problems(
            lesson="demo",
            review=approval("review", lesson="other"),
            release=approval("release", stage="review"),
            **{key: value for key, value in HASHES.items()},
        )
        self.assertTrue(any("not 'demo'" in item for item in problems), problems)
        self.assertTrue(any("stage 'review'" in item for item in problems), problems)

    def test_approval_must_bind_the_hashes(self) -> None:
        problems = approval_problems(
            lesson="demo",
            review=approval("review", final_video_sha256="f" * 64),
            release=None,
            **{key: value for key, value in HASHES.items()},
            require_release=False,
        )
        self.assertTrue(any("final_video" in item for item in problems), problems)

    def test_approval_must_name_a_person(self) -> None:
        problems = approval_problems(
            lesson="demo",
            review=approval("review", approved_by="human"),
            release=None,
            **{key: value for key, value in HASHES.items()},
            require_release=False,
        )
        self.assertTrue(any("named person" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
