"""Report build directories that are not filed under a lesson slug.

CLAUDE.md §16 puts temporary output in build/<slug>/. Isolation runs and
one-off preview folders drift to the top level instead, and then nobody
can tell which of three narration folders is the current one.

Allowed at the top level: lesson slugs (directories that also exist under
lessons/), and a short list of shared areas.
"""
from __future__ import annotations

import sys
from pathlib import Path

SHARED = {
    "_engine-cache", "_smoke", "audit-bundle", "fixtures", "frame-audit",
    "golden", "tmp", "reviews", "static-hold", "static-hold-selftest",
    "contract-negative",
}


def main() -> int:
    build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build")
    lessons = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lessons")
    if not build.is_dir():
        print(f"skip build layout (no {build})")
        return 0
    slugs = {p.name for p in lessons.iterdir() if p.is_dir()} if lessons.is_dir() else set()
    strays = []
    for entry in sorted(build.iterdir()):
        if not entry.is_dir() or entry.name in SHARED or entry.name in slugs:
            continue
        size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1e6
        strays.append((entry.name, size))
    if not strays:
        print("build layout ok")
        return 0
    print(f"{len(strays)} directory/directories at build/ top level are not a lesson slug:")
    for name, size in strays:
        print(f"  {name}  ({size:.1f} MB)")
    print("move them under build/<slug>/<purpose>/ (CLAUDE.md §16)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
