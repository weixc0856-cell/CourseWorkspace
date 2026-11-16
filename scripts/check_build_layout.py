"""Enforce the build/ layout contract (docs/生产流水线-阶段与中间交付物.md §5).

Top level accepts exactly three shared areas plus lesson slugs::

    build/_engine-cache/   engine caches (rebuildable)
    build/_shared/         cross-lesson tool output, one subdirectory per tool
    build/_logs/           regression and run logs
    build/<slug>/          one directory per lesson

Loose files and ad-hoc folders fail: they are how three narration directories
ended up side by side with no way to tell which was current.

Inside a lesson the canonical stage directories are advisory; anything else is
listed so it can be migrated under build/<slug>/tmp/ in the next round.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import yaml

SHARED = {"_engine-cache", "_shared", "_logs"}
LESSON_DIRS = {
    "authoring", "slides", "scenes", "animation", "blender", "narration",
    "tts", "subtitles", "contracts", "timeline", "design", "director",
    "animatic", "preview", "previews", "audio", "sound", "quality", "review",
    "final", "producer", "production", "runtime", "logs", "tmp", "storyboard",
    "qa", "brand", "reports", "release", "analysis", "probe", "frames",
    "stills", "contact", "episode", "public", "provenance", "code", "voice",
    "tools", "blueprint", "retime", "_review", "static-hold", "sample-frames",
    "pilot",
}


def project_ids(projects: Path | None) -> set[str]:
    if projects is None or not projects.is_dir():
        return set()
    ids = set()
    for manifest in projects.rglob("project.yaml"):
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        value = str((data.get("project") or {}).get("id") or "").strip()
        if value:
            ids.add(value)
    return ids


def audit(
    build: Path,
    lessons: Path,
    fixtures: Path | None = None,
    projects: Path | None = None,
) -> tuple[list[str], list[str], int]:
    slugs = {p.name for p in lessons.iterdir() if p.is_dir()} if lessons.is_dir() else set()
    # Test fixtures are lessons too: check.ps1 rebuilds their media in the
    # content root before validating them.  Their slugs are declared by the
    # fixture directory, never guessed from a name prefix.
    fixture_slugs = (
        {p.name for p in fixtures.iterdir() if p.is_dir()}
        if fixtures is not None and fixtures.is_dir()
        else set()
    )
    project_slugs = project_ids(projects)
    errors: list[str] = []
    advice: list[str] = []
    seen_lessons = 0
    for entry in sorted(build.iterdir()):
        if entry.is_dir():
            if (
                entry.name in SHARED
                or entry.name in slugs
                or entry.name in fixture_slugs
                or entry.name in project_slugs
            ):
                if entry.name in slugs:
                    seen_lessons += 1
                    for child in sorted(entry.iterdir()):
                        if child.is_dir() and child.name not in LESSON_DIRS:
                            advice.append(f"{entry.name}/{child.name}/")
                continue
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1e6
            errors.append(
                f"{entry.name}/  ({size:.1f} MB) is neither a lesson slug, a project id "
                "nor a shared area"
            )
        else:
            errors.append(f"{entry.name} is a loose file at the build/ top level")
    if seen_lessons == 0 and slugs:
        advice.append("no lesson build directory exists yet")
    return errors, advice, len(slugs)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        return selftest()
    args = [a for a in args if not a.startswith("--")]
    build = Path(args[0]) if len(args) > 0 else Path("build")
    lessons = Path(args[1]) if len(args) > 1 else Path("lessons")
    fixtures = Path(args[2]) if len(args) > 2 else None
    projects = Path(args[3]) if len(args) > 3 else None
    if not build.is_dir():
        print(f"skip build layout (no {build})")
        return 0
    errors, advice, lesson_count = audit(build, lessons, fixtures, projects)
    if errors:
        print(f"{len(errors)} entry/entries at build/ top level break the layout contract:")
        for line in errors:
            print(f"  {line}")
        print("allowed: _engine-cache/ _shared/ _logs/ <lesson-slug>/ <project-id>/")
        print("put transient output under build/_shared/<tool>/ or build/<slug>/tmp/")
        return 1
    print(f"build layout ok ({lesson_count} lesson dirs, {len(SHARED)} shared areas)")
    if advice:
        print(f"advisory: {len(advice)} non-canonical lesson subdirectories")
        for line in advice[:10]:
            print(f"  {line}")
        if len(advice) > 10:
            print(f"  ... and {len(advice) - 10} more")
    return 0


def selftest() -> int:
    """A check that cannot go red is not a check."""
    root = Path(tempfile.mkdtemp(prefix="build-layout-"))
    try:
        (root / "lessons" / "demo").mkdir(parents=True)
        build = root / "build"
        (build / "demo" / "final").mkdir(parents=True)
        (build / "_shared" / "golden").mkdir(parents=True)
        if audit(build, root / "lessons", root / "lessons")[0]:
            print("selftest FAIL: a clean tree was rejected")
            return 1
        projects = root / "projects"
        (projects / "topic").mkdir(parents=True)
        (projects / "topic" / "project.yaml").write_text(
            "project:\n  id: topic-demo\n", encoding="utf-8"
        )
        (build / "topic-demo" / "preview").mkdir(parents=True)
        if audit(build, root / "lessons", root / "lessons", projects)[0]:
            print("selftest FAIL: a declared project id was rejected")
            return 1
        (build / "demo" / "stills-old").mkdir()
        clean_errors, advice, _ = audit(build, root / "lessons", root / "lessons", projects)
        if clean_errors or "demo/stills-old/" not in advice:
            print("selftest FAIL: a non-canonical lesson subdirectory was not reported")
            return 1
        (build / "stray-run").mkdir()
        (build / "loose.log").write_text("x", encoding="utf-8")
        errors, _, _ = audit(build, root / "lessons", root / "lessons", projects)
        if len(errors) != 2 or not any("stray-run" in e for e in errors) or not any("loose.log" in e for e in errors):
            print(f"selftest FAIL: expected a stray directory and a loose file, got {errors}")
            return 1
        print("build layout selftest PASS")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
