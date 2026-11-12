from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.platform.vendor import audit, sync, vendor_path


class VendorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.source = vendor_path(self.workspace)
        self.source.parent.mkdir(parents=True)
        self.source.write_text("// three r160\n", encoding="utf-8")
        for name in ("shot-a", "shot-b"):
            project = self.workspace / "CodeVideoStudio" / "shots" / name
            project.mkdir(parents=True)
            (project / "index.html").write_text(
                '<script type="importmap">'
                '{"imports": {"three": "./three.module.js"}}</script>',
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sync_copies_once_and_is_idempotent(self) -> None:
        projects = [
            self.workspace / "CodeVideoStudio" / "shots" / "shot-a",
            self.workspace / "CodeVideoStudio" / "shots" / "shot-b",
        ]
        first = sync(self.workspace, projects)
        self.assertEqual(sorted(first["copied"]), ["shot-a", "shot-b"])
        second = sync(self.workspace, projects)
        self.assertEqual(second["copied"], [])
        self.assertEqual(sorted(second["current"]), ["shot-a", "shot-b"])

    def test_audit_reports_missing_and_diverged_copies(self) -> None:
        target = self.workspace / "CodeVideoStudio" / "shots" / "shot-a" / "three.module.js"
        target.write_text("// old\n", encoding="utf-8")
        problems = audit(self.workspace)
        self.assertTrue(any("differs" in item for item in problems))
        self.assertTrue(any("missing" in item for item in problems))
        sync(self.workspace, [self.workspace / "CodeVideoStudio" / "shots" / "shot-a"])
        problems = audit(self.workspace)
        self.assertFalse(any("shot-a" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
