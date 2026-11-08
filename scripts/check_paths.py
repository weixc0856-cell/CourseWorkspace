"""Fail when tracked text files contain machine-specific absolute paths."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]:[\\/]|/Users/)")
ALLOW = (
    "docs/archive/",
    "docs/提交前检查清单.md",
    "CourseControl/tests/test_contracts_v1.py",
    "CourseControl/docker/",
    "scripts/check_paths.py",
)
ALLOW_SUFFIX = ("package-lock.json", "uv.lock")


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    )
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def main() -> int:
    violations: list[str] = []
    for name in tracked_files():
        if name.startswith(ALLOW) or name.endswith(ALLOW_SUFFIX):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                violations.append(f"{name}:{number}: {line.strip()}")
    if violations:
        print("\n".join(violations))
        print(f"path check failed: {len(violations)} machine-specific path(s)")
        return 1
    print("path check ok")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
