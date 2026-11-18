"""CLI wrapper for the shared course-plan chain."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from course_control.production.course_chain import (
    check_course_chain,
    check_lesson_course_chain,
    resolve_chain_root,
)

CURRICULUM = """```yaml curriculum
course: demo
modules:
  - {id: T1, count: 80}
```
"""

DETAIL = """| 集 | 集名 | 原书小节 | 页码 | 时长 |
| --- | --- | --- | --- | --- |
| T1-01 | Demo Lesson | 1.1 Scope | 22–27 | 12 |
"""


def selftest() -> None:
    from tempfile import TemporaryDirectory

    import yaml

    with TemporaryDirectory() as temp:
        root = Path(temp)
        course_root = root / "runtime/course-content/demo"
        course_root.mkdir(parents=True)
        plan = course_root / "COURSE_MAP.md"
        plan.write_text(
            CURRICULUM + DETAIL + "t1-01-demo-lesson\n",
            encoding="utf-8",
        )
        card = course_root / "episodes" / "T1-01" / "card.yaml"
        card.parent.mkdir(parents=True)
        card.write_text(
            yaml.safe_dump(
                {
                    "episode": "T1-01",
                    "title": "Demo Lesson",
                    "section": "1.1",
                    "concepts": ["1.1"],
                    "figures": [],
                    "target_seconds": 720,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        lesson = root / "lessons/t1-01-demo-lesson"
        (lesson / "authoring").mkdir(parents=True)
        (lesson / "lesson.yaml").write_text(
            "schema_version: 1\n"
            "lesson_id: t1-01-demo-lesson\n"
            "course_id: demo\n"
            "episode_id: T1-01\n"
            "duration:\n  target_seconds: 720\n"
            "  min_seconds: 480\n  max_seconds: 900\n",
            encoding="utf-8",
        )
        (lesson / "slides.md").write_text("opening page\n", encoding="utf-8")
        (lesson / "lecture_notes.md").write_text("notes\n", encoding="utf-8")
        (lesson / "authoring/episode.spec.yaml").write_text(
            yaml.safe_dump(
                {
                    "target_seconds": 720,
                    "min_seconds": 480,
                    "max_seconds": 900,
                    "claims": [{"id": "C01", "source": {"chapter": "1", "section": "1.1"}}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        config = root / "course-chain.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 2,
                    "courses": {
                        "demo": {
                            "expected_episode_count": 80,
                            "plan": "runtime/course-content/demo/COURSE_MAP.md",
                            "cards_dir": "runtime/course-content/demo/episodes",
                            "lessons_root": "lessons",
                            "forbidden_lesson_slugs": {"aero-demo": "T1-01"},
                            "forbidden_slide_terms": ["episode 1 of 90"],
                        }
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        good = check_lesson_course_chain(root, lesson, config_path=config)
        if good is None or not good.ok:
            raise SystemExit(f"selftest good chain failed: {good.errors if good else 'unbound'}")
        if good.discovered_episode_count != 80:
            raise SystemExit("selftest did not expand the 80 slots")
        # Wrong theme in the plan row must go red.
        plan.write_text(CURRICULUM + DETAIL.replace("Demo Lesson", "Scope Overview"), encoding="utf-8")
        bad = check_course_chain(
            root, config_path=config, course_id="demo", episode_id="T1-01", lesson_dir=lesson
        )
        if bad.ok:
            raise SystemExit("selftest failed to detect card/plan title drift")
        # A curriculum block that no longer expands to the declared count.
        config_data = yaml.safe_load(config.read_text(encoding="utf-8"))
        config_data["courses"]["demo"]["expected_episode_count"] = 81
        config.write_text(yaml.safe_dump(config_data), encoding="utf-8")
        mismatch = check_course_chain(root, config_path=config, course_id="demo")
        if mismatch.ok:
            raise SystemExit("selftest failed to detect episode-count drift")
        # The resolved chain root must be the content root, not the workspace.
        if resolve_chain_root(root, lesson) != root:
            raise SystemExit("selftest resolved the wrong chain root")
    print("course chain selftest: PASS")


def _bound_lessons(root: Path, course_id: str) -> list[Path]:
    lessons: list[Path] = []
    base = root / "lessons"
    if not base.is_dir():
        return lessons
    for lesson_file in sorted(base.glob("*/lesson.yaml")):
        data = yaml.safe_load(lesson_file.read_text(encoding="utf-8")) or {}
        if str(data.get("course_id") or "") == course_id:
            lessons.append(lesson_file.parent)
    return lessons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-root", type=Path)
    parser.add_argument("--course", default="automotive-aerodynamics")
    parser.add_argument("--episode")
    parser.add_argument("--lesson")
    parser.add_argument("--all", action="store_true", help="check every lesson bound to the course")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.selftest:
        selftest()
        return
    if args.content_root is None:
        parser.error("--content-root is required")
    root = args.content_root.resolve()
    config = args.config or repo / "config" / "course-chain.yaml"

    if args.all:
        lessons = _bound_lessons(root, args.course)
        if not lessons:
            print(f"{args.course}: no lesson declares course_id {args.course!r}", file=sys.stderr)
            raise SystemExit(1)
        failed = False
        for lesson in lessons:
            result = check_lesson_course_chain(root, lesson, config_path=config)
            if result is None or not result.ok:
                failed = True
                for error in (result.errors if result else ["lesson is not bound to the course"]):
                    print(f"  [{lesson.name}] {error}")
                continue
            print(
                f"plan: {result.plan} "
                f"({result.discovered_episode_count}/{result.expected_episode_count} episodes)"
            )
            print(f"{args.course}: PASS ({result.episode_id} -> {lesson.name})")
        if failed:
            raise SystemExit(1)
        return

    lesson_dir = None
    if args.lesson:
        lesson_dir = root / "lessons" / args.lesson
    result = check_course_chain(
        root,
        config_path=config,
        course_id=args.course,
        episode_id=args.episode,
        lesson_dir=lesson_dir,
    )
    if result.plan:
        print(
            f"plan: {result.plan} "
            f"({result.discovered_episode_count}/{result.expected_episode_count} episodes)"
        )
    if result.ok:
        print(f"{args.course}: PASS" + (f" ({args.episode})" if args.episode else ""))
        return
    for error in result.errors:
        print(f"  [error] {error}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
