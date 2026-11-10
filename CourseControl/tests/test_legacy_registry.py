from __future__ import annotations

import unittest

from course_control.legacy_registry import LEGACY_FIELDS, audit, problems


class LegacyRegistryTest(unittest.TestCase):
    def test_registered_fields_pass(self) -> None:
        payload = {
            "video": [
                {"metadata": {"legacy_kind": "slide", "legacy_slide": 1}},
                {"metadata": {"legacy_motion": {"scale": 1.05}}},
            ],
            "legacy_total_duration_s": 12.0,
        }
        self.assertEqual(problems(payload), [])
        report = audit(payload)
        self.assertEqual(
            report["registered"], ["legacy_kind", "legacy_motion", "legacy_slide", "legacy_total_duration_s"]
        )

    def test_unregistered_field_is_reported(self) -> None:
        payload = {"video": [{"metadata": {"legacy_audio_bed": "x"}}]}
        issues = problems(payload)
        self.assertEqual(len(issues), 1)
        self.assertIn("legacy_audio_bed", issues[0])

    def test_every_registered_field_declares_owner_and_removal(self) -> None:
        for name, field in LEGACY_FIELDS.items():
            self.assertTrue(field.consumer, name)
            self.assertTrue(field.replacement, name)
            self.assertTrue(field.removal, name)


if __name__ == "__main__":
    unittest.main()
