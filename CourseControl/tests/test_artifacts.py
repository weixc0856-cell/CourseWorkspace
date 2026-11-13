from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.platform.artifacts import (
    ArtifactRegistry,
    entry_for_file,
    find,
    load_registry,
    mark_missing,
    rebuild_from_build,
    register,
    registry_path,
    save_registry,
)


class ArtifactRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.build = self.root / "build" / "demo"
        (self.build / "final").mkdir(parents=True)
        (self.build / "quality").mkdir(parents=True)
        (self.build / "final" / "final.mp4").write_bytes(b"video")
        (self.build / "quality" / "media-qc.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rebuild_indexes_every_file_with_a_stable_id(self) -> None:
        registry = rebuild_from_build(self.build, "demo")
        self.assertEqual(len(registry.artifacts), 2)
        ids = [item.id for item in registry.artifacts]
        self.assertIn("art.final.final.mp4", ids)
        self.assertIn("art.quality.media-qc.json", ids)
        self.assertEqual(
            find(registry, "art.quality.media-qc.json").kind,
            "report",
        )

        again = rebuild_from_build(self.build, "demo")
        self.assertEqual([item.id for item in again.artifacts], ids)

    def test_register_replaces_by_id(self) -> None:
        registry = rebuild_from_build(self.build, "demo")
        entry = entry_for_file(self.build / "final" / "final.mp4", self.build, produced_by="compose")
        updated = register(registry, entry)
        self.assertEqual(len(updated.artifacts), len(registry.artifacts))
        self.assertEqual(find(updated, entry.id).produced_by, "compose")

    def test_mark_missing_keeps_the_record(self) -> None:
        registry = rebuild_from_build(self.build, "demo")
        (self.build / "final" / "final.mp4").unlink()
        updated = mark_missing(registry, self.build)
        self.assertEqual(len(updated.artifacts), 2)
        self.assertEqual(find(updated, "art.final.final.mp4").status, "missing")
        self.assertEqual(find(updated, "art.quality.media-qc.json").status, "present")

    def test_save_and_load_round_trip(self) -> None:
        registry = rebuild_from_build(self.build, "demo")
        target = registry_path(self.root, "demo")
        save_registry(registry, target)
        loaded = load_registry(target)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.project_id, "demo")
        self.assertEqual(len(loaded.artifacts), 2)

    def test_corrupt_index_reads_as_none(self) -> None:
        target = self.root / "registry.json"
        target.write_text("{not json", encoding="utf-8")
        self.assertIsNone(load_registry(target))
