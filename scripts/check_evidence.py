"""Report build/ paths referenced by docs that no longer exist.

This is a diagnostic, not a release gate.  Historical evidence is allowed to
disappear; it must not silently claim to exist.  Use ``--strict`` in CI if the
project decides every referenced path must be retained.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PATH_RE = re.compile(r"build/[A-Za-z0-9_.\-/]+")
SKIP = ("<", ">", "{", "}", "*", "...", "slug", "lesson", "xxx", "…")


def referenced_paths(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for doc in sorted((root / "docs").rglob("*.md")):
        text = doc.read_text(encoding="utf-8", errors="replace")
        for match in PATH_RE.finditer(text):
            value = match.group(0).rstrip(".,;:)】")
            if any(token in value for token in SKIP):
                continue
            found.setdefault(value, []).append(str(doc.relative_to(root)))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = args.workspace.resolve()
    found = referenced_paths(root)
    missing = {path: docs for path, docs in found.items() if not (root / path).exists()}
    report = root / "build" / ".audit" / "missing-evidence.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"referenced build paths: {len(found)}",
        f"missing: {len(missing)}",
        "",
    ]
    for path in sorted(missing):
        lines.append(f"{path}\t{', '.join(sorted(set(missing[path]))[:3])}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"evidence: {len(found)} referenced, {len(missing)} missing")
    print(f"report: {report}")
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
