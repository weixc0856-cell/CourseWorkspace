"""Recompute the content-root change manifest without following junctions.

The manifest is evidence for moves outside Git.  This script is the verifier so
a reviewer does not have to re-derive the tree algorithm:

    python scripts/verify_content_manifest.py \
        --manifest docs/audit/content-changes-2026-11-16.json \
        --content-root D:/CourseContent

It exits 1 and names every mismatch.  Cache directories are counted, not
hashed; the manifest says which ones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree(path: Path, exclude: tuple[str, ...] = ()) -> dict:
    lines: list[str] = []
    total = 0
    count = 0
    links: list[str] = []
    if path.is_dir():
        for current, dirnames, filenames in os.walk(path, followlinks=False):
            base = Path(current)
            for name in sorted(list(dirnames)):
                child = base / name
                if child.is_symlink() or getattr(child, "is_junction", lambda: False)():
                    links.append(child.relative_to(path).as_posix())
                    dirnames.remove(name)
            for name in sorted(filenames):
                item = base / name
                if item.is_symlink():
                    links.append(item.relative_to(path).as_posix())
                    continue
                relative = item.relative_to(path).as_posix()
                if any(relative.startswith(prefix) for prefix in exclude):
                    continue
                size = item.stat().st_size
                total += size
                count += 1
                lines.append(f"{relative}\0{size}\0{_sha(item)}")
    else:
        size = path.stat().st_size
        total = size
        count = 1
        lines.append(f"{path.name}\0{size}\0{_sha(path)}")
    return {
        "files": count,
        "bytes": total,
        "symlinks": sorted(links),
        "tree_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--content-root", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.content_root.resolve()
    problems: list[str] = []
    for item in data.get("moves") or []:
        target = root / str(item.get("to") or "")
        if item.get("cache"):
            if not target.exists():
                problems.append(f"cache directory missing: {item.get('to')}")
            continue
        if not target.exists():
            problems.append(f"moved item missing: {item.get('to')}")
            continue
        current = tree(target, tuple(item.get("exclude") or ()))
        if current["tree_sha256"] != item.get("tree_sha256"):
            problems.append(f"tree hash mismatch: {item.get('to')}")
        if current["files"] != item.get("files"):
            problems.append(
                f"file count mismatch: {item.get('to')} "
                f"({current['files']} != {item.get('files')})"
            )
        if sorted(current["symlinks"]) != sorted(item.get("symlinks") or []):
            problems.append(f"symlink list mismatch: {item.get('to')}")
    for item in data.get("created") or []:
        path = root / str(item.get("path") or "")
        if not path.is_file():
            problems.append(f"created file missing: {item.get('path')}")
        elif _sha(path) != item.get("sha256"):
            problems.append(f"created file changed: {item.get('path')}")
    for item in data.get("archived") or []:
        path = root / str(item.get("to") or "")
        if not path.is_file():
            problems.append(f"archived file missing: {item.get('to')}")
        elif _sha(path) != item.get("sha256"):
            problems.append(f"archived file changed: {item.get('to')}")
    if problems:
        print(f"{len(problems)} content manifest problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("content manifest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
