from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from course_control.quality.exceptions import (
    ExceptionQueueError,
    blocking_exception,
    legacy_queue_path,
    legacy_shared_path,
    load_lesson_queue,
    load_shared_index,
    open_exceptions,
    queue_path,
    record_observation,
    shared_path,
)

PAST = "2026-11-15T10:00:00+00:00"


def iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(
        timespec="seconds"
    )


ENTRY = {
    "schema_version": 1,
    "check": "episode assembly",
    "lesson": "demo",
    "owner": "Wei Chen",
    "scope": "RemotionStudio/src/episode/timing.json",
    "status": "incomplete",
    "reason": "43 required props are unset",
    "clear_when": "timing.json sets every required prop",
    "release_policy": "release-check and package return incomplete",
    "captured": PAST,
}


def cleared_entry(**overrides) -> dict:
    entry = dict(
        ENTRY,
        status="cleared",
        cleared_by="Wei Chen",
        cleared_at=iso(-120),
        rechecked_at=iso(-60),
    )
    entry.update(overrides)
    return entry


class ContentExceptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.content = Path(self._tmp.name) / "content"
        self.build = self.content / "build" / "demo"
        self.build.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _queue(self, *entries: dict, schema: object = 1) -> None:
        self._write(
            queue_path(self.build),
            {"schema_version": schema, "entries": list(entries)},
        )

    def _index(self, data: object) -> None:
        self._write(shared_path(self.build), data)

    def _legacy(self, data: object) -> None:
        self._write(legacy_shared_path(self.build), data)

    # -- reader ---------------------------------------------------------

    def test_no_queue_blocks_nothing(self) -> None:
        self.assertEqual(open_exceptions(self.build, "demo"), ([], []))
        self.assertIsNone(blocking_exception(self.build, "demo"))

    def test_open_exception_blocks_with_owner_and_condition(self) -> None:
        self._queue(ENTRY)
        blocking, problems = open_exceptions(self.build, "demo")
        self.assertEqual(problems, [])
        self.assertEqual(len(blocking), 1)
        self.assertIn("43 required props", blocking[0]["reason"])
        self.assertEqual(blocking[0]["owner"], "Wei Chen")

    def test_missing_clear_when_is_invalid_and_blocks(self) -> None:
        entry = dict(ENTRY)
        entry.pop("clear_when")
        self._queue(entry)
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("clear_when" in item for item in problems), problems)

    def test_entries_null_blocks(self) -> None:
        self._write(queue_path(self.build), {"schema_version": 1, "entries": None})
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertEqual(blocking, [])
        self.assertTrue(any("entries is missing" in item for item in problems), problems)
        self.assertIsNotNone(blocking_exception(self.build, "demo"))

    def test_entries_missing_blocks(self) -> None:
        self._write(queue_path(self.build), {"schema_version": 1})
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("entries is missing" in item for item in problems), problems)

    def test_non_utf8_queue_blocks_instead_of_raising(self) -> None:
        queue_path(self.build).parent.mkdir(parents=True)
        queue_path(self.build).write_bytes(b'{"schema_version": 1, "entries": [\xff]}')
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertEqual(blocking, [])
        self.assertTrue(any("unreadable" in item for item in problems), problems)
        self.assertIsNotNone(blocking_exception(self.build, "demo"))

    def test_cleared_requires_a_named_clearer_and_valid_times(self) -> None:
        entry = dict(ENTRY, status="cleared")
        self._queue(entry)
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("named clearer" in item for item in problems), problems)
        self.assertTrue(any("cleared_at" in item for item in problems), problems)
        self.assertTrue(any("rechecked_at" in item for item in problems), problems)

    def test_cleared_with_valid_times_releases_the_lesson(self) -> None:
        self._queue(cleared_entry())
        self.assertEqual(load_lesson_queue(self.build, "demo"), ([], []))
        self.assertIsNone(blocking_exception(self.build, "demo"))

    def test_naive_time_blocks(self) -> None:
        self._queue(
            cleared_entry(cleared_at="2026-11-15T10:00:00", rechecked_at=iso(-60))
        )
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("timezone" in item for item in problems), problems)

    def test_future_time_blocks(self) -> None:
        self._queue(cleared_entry(rechecked_at=iso(60)))
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("future" in item for item in problems), problems)

    def test_rechecked_before_cleared_blocks(self) -> None:
        self._queue(
            cleared_entry(cleared_at=iso(-30), rechecked_at=iso(-60))
        )
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("rechecked before" in item for item in problems), problems)

    def test_resolved_needs_check_and_run(self) -> None:
        entry = dict(
            ENTRY,
            status="resolved",
            resolved_at=iso(-10),
            resolved_by_check="episode assembly",
        )
        self._queue(entry)
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("resolved_run" in item for item in problems), problems)

    def test_resolved_with_all_fields_is_not_blocking(self) -> None:
        entry = dict(
            ENTRY,
            status="resolved",
            resolved_at=iso(-10),
            resolved_by_check="episode assembly",
            resolved_run="check:2026-11-16T15:00:00Z",
        )
        self._queue(entry)
        self.assertEqual(load_lesson_queue(self.build, "demo"), ([], []))

    def test_observation_going_back_in_time_blocks(self) -> None:
        entry = dict(
            ENTRY,
            observations=[
                {"at": iso(-10), "status": "incomplete", "by": "episode assembly"},
                {"at": iso(-20), "status": "incomplete", "by": "episode assembly"},
            ],
        )
        self._queue(entry)
        problems = load_lesson_queue(self.build, "demo")[1]
        self.assertTrue(any("goes back in time" in item for item in problems), problems)

    def test_placeholder_owner_blocks(self) -> None:
        self._queue(dict(ENTRY, owner="unassigned"))
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("named person" in item for item in problems), problems)

    def test_wildcard_lesson_blocks_instead_of_matching_everything(self) -> None:
        self._queue(dict(ENTRY, lesson="*"))
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("not 'demo'" in item for item in problems), problems)

    def test_unknown_status_is_invalid(self) -> None:
        self._queue(dict(ENTRY, status="resolved-ish"))
        blocking, problems = load_lesson_queue(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("invalid exception entry" in item for item in problems), problems)

    def test_checks_report_at_the_old_path_is_ignored(self) -> None:
        self._write(
            legacy_queue_path(self.build),
            {"schema_version": 1, "lesson": "demo", "stage": "spec", "results": [], "exceptions": []},
        )
        self.assertEqual(open_exceptions(self.build, "demo"), ([], []))

    def test_legacy_shared_entry_keeps_blocking_and_asks_for_a_move(self) -> None:
        self._legacy({"schema_version": 1, "entries": [ENTRY]})
        blocking, problems = load_shared_index(self.build, "demo")
        self.assertTrue(blocking)
        self.assertTrue(any("must move to" in item for item in problems), problems)

    def test_index_lists_a_lesson_without_a_queue(self) -> None:
        self._index({"schema_version": 1, "lessons_with_open_exceptions": ["demo"]})
        blocking, problems = load_shared_index(self.build, "demo")
        self.assertEqual(problems, [])
        self.assertEqual(len(blocking), 1)
        self.assertIn("queue is missing", blocking[0]["reason"])

    def test_index_with_an_invalid_item_blocks(self) -> None:
        self._index(
            {
                "schema_version": 1,
                "lessons_with_open_exceptions": [{"lesson": "demo"}],
            }
        )
        blocking, problems = load_shared_index(self.build, "demo")
        self.assertTrue(any("invalid lesson id" in item for item in problems), problems)
        self.assertIsNotNone(blocking_exception(self.build, "demo"))

    def test_index_is_not_authoritative_when_the_queue_exists(self) -> None:
        self._index({"schema_version": 1, "lessons_with_open_exceptions": ["demo"]})
        self._queue(cleared_entry())
        self.assertEqual(load_shared_index(self.build, "demo"), ([], []))
        self.assertIsNone(blocking_exception(self.build, "demo"))

    def test_unreadable_shared_file_blocks(self) -> None:
        path = shared_path(self.build)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        problems = load_shared_index(self.build, "demo")[1]
        self.assertTrue(any("unreadable" in item for item in problems), problems)
        self.assertIsNotNone(blocking_exception(self.build, "demo"))

    def test_release_check_uses_the_same_reader(self) -> None:
        from course_control.release.check import content_exception_for

        self._queue(ENTRY)
        exception = content_exception_for(self.build, "demo")
        self.assertIsNotNone(exception)
        self.assertIn("43 required props", exception["reason"])

    # -- writer ---------------------------------------------------------

    def _entries(self) -> list[dict]:
        return json.loads(queue_path(self.build).read_text(encoding="utf-8"))["entries"]

    def test_writer_creates_an_entry_and_appends_history(self) -> None:
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        entries = self._entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status"], "incomplete")
        self.assertEqual(len(entries[0]["observations"]), 2)

    def test_passing_check_writes_resolved_and_keeps_the_entry(self) -> None:
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        record_observation(
            self.build, "demo", "episode assembly", resolved=True, run_id="check:1"
        )
        entries = self._entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["status"], "resolved")
        self.assertEqual(entries[0]["resolved_run"], "check:1")
        self.assertIsNone(blocking_exception(self.build, "demo"))

    def test_passing_check_without_a_record_writes_nothing(self) -> None:
        result = record_observation(self.build, "demo", "episode assembly", resolved=True)
        self.assertEqual(result["status"], "none")
        self.assertFalse(queue_path(self.build).exists())

    def test_resolved_returns_to_incomplete(self) -> None:
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        record_observation(self.build, "demo", "episode assembly", resolved=True)
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertEqual(self._entries()[0]["status"], "incomplete")

    def test_cleared_reopens_only_after_rechecked_at(self) -> None:
        self._queue(cleared_entry())
        record_observation(
            self.build,
            "demo",
            "episode assembly",
            resolved=False,
            observed_at=iso(-30),
        )
        entry = self._entries()[0]
        self.assertEqual(entry["status"], "incomplete")
        stored = [
            item for item in entry["observations"] if item["status"] == "cleared"
        ]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["by"], "Wei Chen")

    def test_old_failure_does_not_reopen_a_clear(self) -> None:
        self._queue(cleared_entry())
        record_observation(
            self.build,
            "demo",
            "episode assembly",
            resolved=False,
            observed_at=iso(-90),
        )
        entry = self._entries()[0]
        self.assertEqual(entry["status"], "cleared")
        self.assertIsNone(blocking_exception(self.build, "demo"))

    def test_writer_refuses_another_lessons_entry(self) -> None:
        self._queue(dict(ENTRY, lesson="other"))
        before = queue_path(self.build).read_bytes()
        with self.assertRaises(ExceptionQueueError):
            record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertEqual(queue_path(self.build).read_bytes(), before)

    def test_corrupt_queue_is_not_overwritten(self) -> None:
        queue_path(self.build).parent.mkdir(parents=True)
        before = b'{"schema_version": 1, "entries": [oops'
        queue_path(self.build).write_bytes(before)
        with self.assertRaises(ExceptionQueueError):
            record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertEqual(queue_path(self.build).read_bytes(), before)

    def test_missing_entries_is_not_empty_for_the_writer(self) -> None:
        self._write(queue_path(self.build), {"schema_version": 1})
        before = queue_path(self.build).read_bytes()
        with self.assertRaises(ExceptionQueueError):
            record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertEqual(queue_path(self.build).read_bytes(), before)

    def test_corrupt_index_is_not_overwritten(self) -> None:
        self._index({"schema_version": 1, "lessons_with_open_exceptions": "demo"})
        before = shared_path(self.build).read_bytes()
        with self.assertRaises(ExceptionQueueError):
            record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertFalse(queue_path(self.build).exists())
        self.assertEqual(shared_path(self.build).read_bytes(), before)

    def test_legacy_shared_keeps_other_checks(self) -> None:
        other = dict(ENTRY, check="other check")
        self._legacy({"schema_version": 1, "entries": [ENTRY, other]})
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        remaining = json.loads(legacy_shared_path(self.build).read_text("utf-8"))["entries"]
        self.assertEqual([item["check"] for item in remaining], ["other check"])

    def test_legacy_lesson_queue_migrates_and_frees_the_checks_path(self) -> None:
        self._write(
            legacy_queue_path(self.build),
            {"schema_version": 1, "entries": [ENTRY]},
        )
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertTrue(queue_path(self.build).is_file())
        self.assertFalse(legacy_queue_path(self.build).exists())
        self.assertEqual(self._entries()[0]["owner"], "Wei Chen")

    def test_checks_report_is_never_touched(self) -> None:
        report = {
            "schema_version": 1,
            "lesson": "demo",
            "stage": "spec",
            "results": [],
            "exceptions": [],
        }
        self._write(legacy_queue_path(self.build), report)
        before = legacy_queue_path(self.build).read_bytes()
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        self.assertEqual(legacy_queue_path(self.build).read_bytes(), before)
        self.assertTrue(queue_path(self.build).is_file())

    def test_writer_keeps_a_human_owner(self) -> None:
        self._queue(ENTRY)
        record_observation(
            self.build, "demo", "episode assembly", resolved=False, owner="unassigned"
        )
        self.assertEqual(self._entries()[0]["owner"], "Wei Chen")

    def test_index_tracks_the_blocking_state(self) -> None:
        record_observation(self.build, "demo", "episode assembly", resolved=False)
        index = json.loads(shared_path(self.build).read_text("utf-8"))
        self.assertEqual(index["lessons_with_open_exceptions"], ["demo"])
        record_observation(self.build, "demo", "episode assembly", resolved=True)
        index = json.loads(shared_path(self.build).read_text("utf-8"))
        self.assertEqual(index["lessons_with_open_exceptions"], [])


if __name__ == "__main__":
    unittest.main()
