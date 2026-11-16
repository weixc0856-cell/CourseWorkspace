"""Content exceptions: per-lesson evidence, a named owner, a clear condition.

The authoritative queue is per lesson::

    build/<slug>/quality/content-exceptions.json

``build/<slug>/quality/exceptions.json`` belongs to ``course-control checks``
and is never read or written here.

The shared file (``build/_shared/exceptions/index.json``) is an index of
lessons with blocking exceptions.  The old shared queue and the old per-lesson
path are imports only: they keep blocking until they are migrated, and the
writer migrates the old per-lesson queue on its first run.

Current state and history are separate.  The entry's ``status`` says what is
true now; ``observations`` keeps every check and every human decision that led
there, so a later failure never overwrites the record of an earlier clear.

Every rule fails closed:

- an entry that does not bind this lesson, a named owner, a reason, a
  ``clear_when`` condition and a valid time blocks the lesson;
- ``cleared`` needs ``cleared_by`` (a named person), ``cleared_at`` and
  ``rechecked_at`` (ISO 8601 with a timezone, not in the future, not before
  ``cleared_at``);
- ``resolved`` is a machine observation: ``resolved_at``,
  ``resolved_by_check`` and ``resolved_run`` are required, and it never closes
  a human clear;
- a malformed queue, index or legacy file blocks instead of reading as "no
  exception"; the writer refuses and leaves every file byte-identical.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from course_control.content.contracts import StrictModel

QUEUE_REL = Path("quality") / "content-exceptions.json"
CHECKS_REPORT_REL = Path("quality") / "exceptions.json"
SHARED_REL = Path("_shared") / "exceptions" / "index.json"
LEGACY_SHARED_REL = (
    Path("_shared") / "frame-audit" / "episode" / "content-exceptions.json"
)

# A role, a placeholder or a machine is not a person who can own an exception
# or clear one.
MACHINE_NAMES = {
    "",
    "owner",
    "unassigned",
    "human",
    "system",
    "claude",
    "claude code",
    "ai",
    "assistant",
    "automation",
    "bot",
    "n/a",
    "none",
    "unknown",
}

STATUSES = ("open", "incomplete", "cleared", "resolved")
BLOCKING_STATUSES = ("open", "incomplete")
SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
MAX_CLOCK_SKEW = timedelta(minutes=5)


class ExceptionQueueError(RuntimeError):
    """The queue could not be read or written; nothing was changed."""


def named(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in MACHINE_NAMES


def parse_time(value: object, label: str) -> datetime:
    """An ISO 8601 time with a timezone, not in the future."""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is not an ISO 8601 time: {text}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} has no timezone: {text}")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > datetime.now(timezone.utc) + MAX_CLOCK_SKEW:
        raise ValueError(f"{label} is in the future: {text}")
    return parsed


class Observation(StrictModel):
    at: str
    status: Literal["open", "incomplete", "cleared", "resolved"]
    by: str
    run: str = ""
    detail: str = ""


class ContentException(StrictModel):
    schema_version: Literal[1] = 1
    check: str
    lesson: str
    owner: str
    scope: str = ""
    status: Literal["open", "incomplete", "cleared", "resolved"] = "incomplete"
    reason: str
    clear_when: str
    release_policy: str = ""
    captured: str = ""
    detail: str | None = None
    next: str | None = None
    cleared_by: str | None = None
    cleared_at: str | None = None
    rechecked_at: str | None = None
    resolved_at: str | None = None
    resolved_by_check: str | None = None
    resolved_run: str | None = None
    observations: list[Observation] = Field(default_factory=list)


def queue_path(build_root: Path) -> Path:
    return Path(build_root) / QUEUE_REL


def legacy_queue_path(build_root: Path) -> Path:
    """The old per-lesson path; ``course-control checks`` owns it now."""
    return Path(build_root) / CHECKS_REPORT_REL


def shared_path(build_root: Path) -> Path:
    return Path(build_root).parent / SHARED_REL


def legacy_shared_path(build_root: Path) -> Path:
    """The old shared queue, kept as a blocking import until it is migrated."""
    return Path(build_root).parent / LEGACY_SHARED_REL


def _read(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "is not a JSON object"
    return data, None


def _schema_version_problem(data: dict, label: str) -> str | None:
    value = data.get("schema_version")
    if type(value) is not int or value != 1:
        return f"{label}: schema_version is {value!r}, not the integer 1"
    return None


def _entries(path: Path, label: str) -> tuple[list, list[str]]:
    if not path.is_file():
        return [], []
    data, problem = _read(path)
    if problem:
        return [], [f"{label}: {problem}"]
    version = _schema_version_problem(data, label)
    if version:
        return [], [version]
    entries = data.get("entries")
    if entries is None:
        return [], [f"{label}: entries is missing"]
    if not isinstance(entries, list):
        return [], [f"{label}: entries is not a list"]
    return entries, []


def _observation_problems(entry: ContentException) -> list[str]:
    problems: list[str] = []
    previous: datetime | None = None
    for index, observation in enumerate(entry.observations):
        label = f"{entry.check or 'exception'} observation #{index + 1}"
        try:
            at = parse_time(observation.at, f"{label} at")
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if previous is not None and at < previous:
            problems.append(f"{label} goes back in time")
        previous = at
        if not str(observation.by or "").strip():
            problems.append(f"{label} has no observer")
        if observation.status == "cleared" and not named(observation.by):
            problems.append(f"{label} was cleared by a non-person")
    return problems


def _time_problems(entry: ContentException) -> list[str]:
    problems: list[str] = []
    label = entry.check or "exception"
    if entry.status == "cleared":
        if not named(entry.cleared_by or ""):
            problems.append(f"{label} was cleared without a named clearer")
        cleared = rechecked = None
        try:
            cleared = parse_time(entry.cleared_at, f"{label} cleared_at")
        except ValueError as exc:
            problems.append(str(exc))
        try:
            rechecked = parse_time(entry.rechecked_at, f"{label} rechecked_at")
        except ValueError as exc:
            problems.append(str(exc))
        if cleared is not None and rechecked is not None and rechecked < cleared:
            problems.append(f"{label} was rechecked before it was cleared")
    elif entry.status == "resolved":
        try:
            parse_time(entry.resolved_at, f"{label} resolved_at")
        except ValueError as exc:
            problems.append(str(exc))
        if not str(entry.resolved_by_check or "").strip():
            problems.append(f"{label} was resolved without resolved_by_check")
        if not str(entry.resolved_run or "").strip():
            problems.append(f"{label} was resolved without resolved_run")
    return problems


def _entry_problems(entry: ContentException, lesson: str) -> list[str]:
    problems: list[str] = []
    if str(entry.lesson or "") != lesson:
        problems.append(
            f"exception entry is for {entry.lesson!r}, not {lesson!r}"
        )
    if not str(entry.reason or "").strip():
        problems.append(f"{entry.check or 'exception'} has no reason")
    if not str(entry.clear_when or "").strip():
        problems.append(f"{entry.check or 'exception'} has no clear_when condition")
    if entry.status in BLOCKING_STATUSES and not named(entry.owner):
        problems.append(
            f"{entry.check or 'exception'} owner {entry.owner!r} is not a named person"
        )
    problems.extend(_time_problems(entry))
    problems.extend(_observation_problems(entry))
    return problems


def _as_blocking(entry: ContentException, problems: list[str]) -> dict:
    return {
        "check": entry.check,
        "lesson": entry.lesson,
        "owner": entry.owner,
        "scope": entry.scope,
        "status": entry.status,
        "reason": str(entry.reason or "").strip() or "open content exception",
        "clear_when": entry.clear_when,
        "detail": entry.detail or "",
        "problems": problems,
    }


def load_lesson_queue(
    build_root: Path, lesson: str
) -> tuple[list[dict], list[str]]:
    """Blocking entries and problems from the per-lesson queue."""
    path = queue_path(build_root)
    if not path.is_file():
        return [], []
    entries, problems = _entries(path, f"lesson queue {path.name}")
    blocking: list[dict] = []
    for index, item in enumerate(entries):
        try:
            entry = ContentException.model_validate(item)
        except Exception as exc:  # noqa: BLE001 - a malformed entry blocks
            problems.append(f"invalid exception entry #{index + 1}: {exc}")
            blocking.append(
                {
                    "check": f"entry #{index + 1}",
                    "lesson": lesson,
                    "owner": "",
                    "scope": "",
                    "status": "incomplete",
                    "reason": f"invalid exception entry: {exc}",
                    "clear_when": "",
                    "detail": "",
                    "problems": [str(exc)],
                }
            )
            continue
        entry_problems = _entry_problems(entry, lesson)
        if entry_problems:
            problems.extend(entry_problems)
        if entry.status in BLOCKING_STATUSES or entry_problems:
            blocking.append(_as_blocking(entry, entry_problems))
    return blocking, problems


def _load_index(
    path: Path, build_root: Path, lesson: str
) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        return [], []
    data, problem = _read(path)
    if problem:
        return [], [f"shared index: {problem}"]
    version = _schema_version_problem(data, "shared index")
    if version:
        return [], [version]
    listed = data.get("lessons_with_open_exceptions")
    if not isinstance(listed, list):
        return [], ["shared index: lessons_with_open_exceptions is not a list"]
    values: list[str] = []
    problems: list[str] = []
    for item in listed:
        if not isinstance(item, str) or not SLUG_RE.fullmatch(item):
            problems.append(f"shared index has an invalid lesson id: {item!r}")
            continue
        values.append(item)
    if problems:
        return [], problems
    if lesson not in values:
        return [], []
    if queue_path(build_root).is_file():
        # The queue is authoritative; the index only guards a missing queue.
        return [], []
    return (
        [
            {
                "check": "shared index",
                "lesson": lesson,
                "owner": "",
                "scope": "",
                "status": "incomplete",
                "reason": (
                    "shared index lists this lesson but the per-lesson queue is "
                    "missing"
                ),
                "clear_when": "",
                "detail": "",
                "problems": [],
            }
        ],
        [],
    )


def _load_legacy(
    path: Path, build_root: Path, lesson: str
) -> tuple[list[dict], list[str]]:
    """The old shared queue: import this lesson's entries and ask for a move."""
    if not path.is_file():
        return [], []
    data, problem = _read(path)
    if problem:
        return [], [f"shared queue: {problem}"]
    version = _schema_version_problem(data, "shared queue")
    if version:
        return [], [version]
    if "lessons_with_open_exceptions" in data:
        return _load_index(path, build_root, lesson)
    entries = data.get("entries")
    if entries is None:
        return [], ["shared queue: entries is missing"]
    if not isinstance(entries, list):
        return [], ["shared queue: entries is not a list"]
    blocking: list[dict] = []
    problems: list[str] = []
    for index, item in enumerate(entries):
        try:
            entry = ContentException.model_validate(item)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"invalid shared entry #{index + 1}: {exc}")
            continue
        if entry.lesson != lesson:
            continue
        problems.append(
            f"shared queue entry '{entry.check}' must move to "
            f"{QUEUE_REL.as_posix()}"
        )
        entry_problems = _entry_problems(entry, lesson)
        if entry_problems:
            problems.extend(entry_problems)
        if entry.status in BLOCKING_STATUSES or entry_problems:
            blocking.append(_as_blocking(entry, entry_problems))
    return blocking, problems


def _load_legacy_lesson_queue(
    build_root: Path, lesson: str
) -> tuple[list[dict], list[str]]:
    """The old per-lesson path, if it still holds a queue rather than a report."""
    path = legacy_queue_path(build_root)
    if not path.is_file():
        return [], []
    data, problem = _read(path)
    if problem:
        return [], [f"legacy lesson queue: {problem}"]
    if "results" in data:
        return [], []  # this is the checks report, not a queue
    if data.get("entries") is None:
        return [], []
    if not isinstance(data.get("entries"), list):
        return [], ["legacy lesson queue: entries is not a list"]
    entries, problems = _entries(path, "legacy lesson queue")
    if problems:
        return [], problems
    blocking: list[dict] = []
    for index, item in enumerate(entries):
        try:
            entry = ContentException.model_validate(item)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"invalid legacy lesson entry #{index + 1}: {exc}")
            continue
        if entry.lesson != lesson:
            continue
        problems.append(
            f"legacy lesson queue entry '{entry.check}' must move to "
            f"{QUEUE_REL.as_posix()}"
        )
        entry_problems = _entry_problems(entry, lesson)
        if entry_problems:
            problems.extend(entry_problems)
        if entry.status in BLOCKING_STATUSES or entry_problems:
            blocking.append(_as_blocking(entry, entry_problems))
    return blocking, problems


def load_shared_index(
    build_root: Path, lesson: str
) -> tuple[list[dict], list[str]]:
    """Blocking entries from the index and both legacy paths, plus problems."""
    index_blocking, index_problems = _load_index(
        shared_path(build_root), build_root, lesson
    )
    legacy_blocking, legacy_problems = _load_legacy(
        legacy_shared_path(build_root), build_root, lesson
    )
    old_lesson_blocking, old_lesson_problems = _load_legacy_lesson_queue(
        build_root, lesson
    )
    return (
        index_blocking + legacy_blocking + old_lesson_blocking,
        index_problems + legacy_problems + old_lesson_problems,
    )


def open_exceptions(build_root: Path, lesson: str) -> tuple[list[dict], list[str]]:
    """Everything that blocks this lesson, from every queue and the index."""
    lesson_blocking, lesson_problems = load_lesson_queue(build_root, lesson)
    shared_blocking, shared_problems = load_shared_index(build_root, lesson)
    return lesson_blocking + shared_blocking, lesson_problems + shared_problems


def blocking_exception(build_root: Path, lesson: str) -> dict | None:
    """One dict for callers that only need to know whether to block."""
    blocking, problems = open_exceptions(build_root, lesson)
    if not blocking and not problems:
        return None
    first = blocking[0] if blocking else {}
    reason = str(first.get("reason") or "").strip()
    if problems:
        extra = "; ".join(problems)
        reason = (reason + " | " if reason else "") + extra
    return {
        "lesson": lesson,
        "check": first.get("check") or "",
        "owner": first.get("owner") or "",
        "scope": first.get("scope") or "",
        "status": first.get("status") or "incomplete",
        "reason": reason or "open content exception",
        "detail": first.get("detail") or "",
        "clear_when": first.get("clear_when") or "",
        "problems": problems,
    }


# -- writer -----------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    os.replace(temp, path)


def _read_queue_for_write(build_root: Path) -> tuple[list[dict], bool]:
    """Return (entries, migrated_from_legacy); raise on anything corrupt."""
    path = queue_path(build_root)
    legacy = legacy_queue_path(build_root)
    if path.is_file() and legacy.is_file():
        data, _ = _read(legacy)
        if data is not None and data.get("entries") is not None and "results" not in data:
            raise ExceptionQueueError(
                "both quality/content-exceptions.json and the legacy "
                "quality/exceptions.json hold a queue; resolve the legacy import first"
            )
    if path.is_file():
        entries, problems = _entries(path, f"lesson queue {path.name}")
        if problems:
            raise ExceptionQueueError("; ".join(problems))
        return entries, False
    if legacy.is_file():
        data, problem = _read(legacy)
        if problem:
            raise ExceptionQueueError(f"legacy lesson queue: {problem}")
        if "results" in data:
            return [], False
        if data.get("entries") is None:
            return [], False
        entries, problems = _entries(legacy, "legacy lesson queue")
        if problems:
            raise ExceptionQueueError("; ".join(problems))
        return entries, True
    return [], False


def _validated_entries(entries: list, lesson: str) -> list[ContentException]:
    validated: list[ContentException] = []
    for index, item in enumerate(entries):
        try:
            entry = ContentException.model_validate(item)
        except Exception as exc:  # noqa: BLE001
            raise ExceptionQueueError(f"invalid exception entry #{index + 1}: {exc}") from exc
        if entry.lesson != lesson:
            raise ExceptionQueueError(
                f"exception entry #{index + 1} is for {entry.lesson!r}, not {lesson!r}"
            )
        schema_problems = _time_problems(entry) + _observation_problems(entry)
        if not str(entry.reason or "").strip():
            schema_problems.append(f"{entry.check or 'exception'} has no reason")
        if not str(entry.clear_when or "").strip():
            schema_problems.append(
                f"{entry.check or 'exception'} has no clear_when condition"
            )
        if schema_problems:
            raise ExceptionQueueError("; ".join(schema_problems))
        if not str(entry.owner or "").strip():
            raise ExceptionQueueError(
                f"{entry.check or 'exception'} has an empty owner"
            )
        validated.append(entry)
    return validated


def _archive_clear(entry: ContentException) -> None:
    if not (entry.cleared_by or entry.cleared_at or entry.rechecked_at):
        return
    entry.observations.append(
        Observation(
            at=entry.rechecked_at or entry.cleared_at or _now(),
            status="cleared",
            by=entry.cleared_by or "",
            detail="human clear preserved when the check failed again",
        )
    )
    entry.cleared_by = None
    entry.cleared_at = None
    entry.rechecked_at = None


def record_observation(
    build_root: Path,
    lesson: str,
    check: str,
    *,
    resolved: bool,
    observed_at: str | None = None,
    run_id: str = "",
    detail: str = "",
    owner: str = "unassigned",
    scope: str = "",
    reason: str = "",
    clear_when: str = "",
    release_policy: str = "",
) -> dict:
    """Record one automatic observation; never writes ``cleared``.

    Nothing is written when any existing file is corrupt.  A human
    ``cleared`` entry is only reopened when the new failure was observed after
    its ``rechecked_at``; an earlier failure leaves the human decision intact.
    A passing check writes ``resolved`` and keeps the entry.
    """
    text = str(check or "").strip()
    if not text:
        raise ExceptionQueueError("check id is empty")
    try:
        at = parse_time(
            observed_at or _now(), f"{text} observed_at"
        )
    except ValueError as exc:
        raise ExceptionQueueError(str(exc)) from exc
    stamp = at.isoformat(timespec="seconds")
    try:
        raw_entries, migrated = _read_queue_for_write(build_root)
        entries = _validated_entries(raw_entries, lesson)
    except ExceptionQueueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExceptionQueueError(str(exc)) from exc

    entry = next(
        (item for item in entries if item.check == text and item.lesson == lesson),
        None,
    )
    if entry is None:
        if resolved:
            # A passing check with no record is not an exception; do not
            # invent history.
            return {"check": text, "lesson": lesson, "status": "none"}
        entry = ContentException(
            check=text,
            lesson=lesson,
            owner=owner,
            scope=scope,
            status="incomplete",
            reason=reason or text,
            clear_when=clear_when or "the check no longer reports this problem",
            release_policy=release_policy,
            captured=stamp,
            detail=detail or None,
            observations=[
                Observation(
                    at=stamp,
                    status="incomplete",
                    by=text,
                    run=run_id,
                    detail=detail,
                )
            ],
        )
        entries.append(entry)
    else:
        if resolved:
            if entry.status == "cleared":
                # A passing check never overrides a human clear.
                entry.observations.append(
                    Observation(
                        at=stamp,
                        status="cleared",
                        by=entry.cleared_by or "",
                        detail="check passed; human clear stands",
                    )
                )
            else:
                entry.status = "resolved"
                entry.resolved_at = stamp
                entry.resolved_by_check = text
                entry.resolved_run = run_id or f"check:{stamp}"
                entry.observations.append(
                    Observation(
                        at=stamp,
                        status="resolved",
                        by=text,
                        run=entry.resolved_run,
                        detail=detail,
                    )
                )
        else:
            if entry.status == "cleared":
                try:
                    rechecked = parse_time(
                        entry.rechecked_at, f"{text} rechecked_at"
                    )
                except ValueError as exc:
                    raise ExceptionQueueError(str(exc)) from exc
                if at > rechecked:
                    _archive_clear(entry)
                    entry.status = "incomplete"
                    entry.observations.append(
                        Observation(
                            at=stamp,
                            status="incomplete",
                            by=text,
                            run=run_id,
                            detail=detail or "check failed after the recheck time",
                        )
                    )
                else:
                    entry.observations.append(
                        Observation(
                            at=stamp,
                            status="cleared",
                            by=entry.cleared_by or "",
                            detail="failure observed before rechecked_at; human clear stands",
                        )
                    )
            else:
                entry.status = "incomplete"
                entry.observations.append(
                    Observation(
                        at=stamp,
                        status="incomplete",
                        by=text,
                        run=run_id,
                        detail=detail,
                    )
                )
            if detail:
                entry.detail = detail
            # Fill what a human has not set yet; never overwrite their owner,
            # scope, reason or clear condition from a regression.
            if not str(entry.owner or "").strip() and owner:
                entry.owner = owner
            if not str(entry.scope or "").strip() and scope:
                entry.scope = scope
            if not str(entry.reason or "").strip() and reason:
                entry.reason = reason
            if not str(entry.clear_when or "").strip() and clear_when:
                entry.clear_when = clear_when
            if not str(entry.release_policy or "").strip() and release_policy:
                entry.release_policy = release_policy

    # Validate the result before touching the files.
    for item in entries:
        problems = _time_problems(item)
        if problems:
            raise ExceptionQueueError("; ".join(problems))

    index_path = shared_path(build_root)
    current_index: object = []
    if index_path.is_file():
        index_data, index_problem = _read(index_path)
        if index_problem:
            raise ExceptionQueueError(f"shared index: {index_problem}")
        version = _schema_version_problem(index_data, "shared index")
        if version:
            raise ExceptionQueueError(version)
        current_index = index_data.get("lessons_with_open_exceptions")
    if not isinstance(current_index, list):
        raise ExceptionQueueError("shared index: lessons_with_open_exceptions is not a list")
    lessons: list[str] = []
    for item in current_index:
        if not isinstance(item, str) or not SLUG_RE.fullmatch(item):
            raise ExceptionQueueError(f"shared index has an invalid lesson id: {item!r}")
        if item not in lessons:
            lessons.append(item)
    blocking_here = any(
        item.status in BLOCKING_STATUSES for item in entries
    )
    if blocking_here and lesson not in lessons:
        lessons.append(lesson)
    if not blocking_here:
        lessons = [item for item in lessons if item != lesson]
    lessons.sort()

    legacy_path = legacy_shared_path(build_root)
    legacy_data: dict | None = None
    if legacy_path.is_file():
        legacy_data, legacy_problem = _read(legacy_path)
        if legacy_problem:
            raise ExceptionQueueError(f"shared queue: {legacy_problem}")
        legacy_version = _schema_version_problem(legacy_data, "shared queue")
        if legacy_version:
            raise ExceptionQueueError(legacy_version)
        if "entries" in legacy_data and not isinstance(legacy_data["entries"], list):
            raise ExceptionQueueError("shared queue: entries is not a list")

    payload = {
        "schema_version": 1,
        "entries": [item.model_dump(mode="json") for item in entries],
    }
    _write_atomic(queue_path(build_root), payload)
    _write_atomic(
        index_path,
        {"schema_version": 1, "lessons_with_open_exceptions": lessons},
    )
    if legacy_data is not None and isinstance(legacy_data.get("entries"), list):
        kept = [
            item
            for item in legacy_data["entries"]
            if not (
                isinstance(item, dict)
                and item.get("lesson") == lesson
                and item.get("check") == text
            )
        ]
        if len(kept) != len(legacy_data["entries"]):
            _write_atomic(
                legacy_path, {"schema_version": 1, "entries": kept}
            )
    if migrated:
        # The old per-lesson file is now free for ``course-control checks``.
        old = legacy_queue_path(build_root)
        data, _ = _read(old)
        if data is not None and "results" not in data and data.get("entries") is not None:
            old.unlink()
    return {
        "check": text,
        "lesson": lesson,
        "status": entry.status,
        "observed_at": stamp,
        "resolved": resolved,
    }


__all__ = [
    "ContentException",
    "ExceptionQueueError",
    "Observation",
    "blocking_exception",
    "load_lesson_queue",
    "legacy_queue_path",
    "legacy_shared_path",
    "load_shared_index",
    "named",
    "open_exceptions",
    "parse_time",
    "queue_path",
    "record_observation",
    "shared_path",
]
