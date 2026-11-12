"""Report and classify build/ paths referenced by docs that no longer exist.

A missing path is not automatically a defect.  It is a defect when nobody has
decided what it was.  Every missing path must match a rule in
``docs/audit/evidence-decisions.yaml``:

    retained       still required evidence; restore it
    regenerable    produced by a documented command; re-run it
    retired_poc    an experiment that left the production path; reference is historical
    historical     archive/document-history reference; not expected to exist
    stale_ref      documentation points at a path that never existed; fix the doc
    external       produced outside this workspace

Unclassified missing paths fail the check, so a new dangling reference cannot
sneak in unnoticed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from course_control.platform.workspace_layout import content_root

PATH_RE = re.compile(r"build/[A-Za-z0-9_.\-/]+")
SKIP = ("<", ">", "{", "}", "*", "...", "slug", "lesson", "xxx", "…")
DISPOSITIONS = {
    "retained",
    "regenerable",
    "retired_poc",
    "historical",
    "stale_ref",
    "external",
}


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


def load_rules(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = data.get("rules") or []
    return [rule for rule in rules if isinstance(rule, dict)]


def classify(path: str, rules: list[dict]) -> dict | None:
    matches = [rule for rule in rules if path.startswith(str(rule.get("prefix") or ""))]
    if not matches:
        return None
    return max(matches, key=lambda rule: len(str(rule.get("prefix") or "")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("docs/audit/evidence-decisions.yaml"),
    )
    args = parser.parse_args()
    root = args.workspace.resolve()
    content = content_root(root)
    found = referenced_paths(root)

    def exists(path: str) -> bool:
        # build/ output lives under the content root, the rest stays in the workspace
        base = content if path.startswith("build/") else root
        return (base / path).exists()

    missing = {path: docs for path, docs in found.items() if not exists(path)}
    rules = load_rules((root / args.decisions) if not args.decisions.is_absolute() else args.decisions)

    classified: dict[str, dict] = {}
    unclassified: list[str] = []
    for path in sorted(missing):
        rule = classify(path, rules)
        if rule is None or rule.get("disposition") not in DISPOSITIONS:
            unclassified.append(path)
            continue
        classified[path] = {
            "disposition": rule["disposition"],
            "reason": rule.get("reason"),
            "owner": rule.get("owner"),
            "referenced_by": sorted(set(missing[path])),
        }

    report = content / "build" / ".audit" / "missing-evidence.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"referenced build paths: {len(found)}",
        f"missing: {len(missing)}",
        f"classified: {len(classified)}",
        f"unclassified: {len(unclassified)}",
        "",
        "path\tdisposition\treason\treferenced_by",
    ]
    for path, item in classified.items():
        lines.append(
            f"{path}\t{item['disposition']}\t{item['reason'] or ''}\t"
            + ", ".join(item["referenced_by"][:3])
        )
    for path in unclassified:
        lines.append(f"{path}\tUNCLASSIFIED\t\t{', '.join(sorted(set(missing[path]))[:3])}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    json_report = content / "build" / ".audit" / "evidence-classification.json"
    json_report.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "referenced": len(found),
                "missing": len(missing),
                "classified": classified,
                "unclassified": unclassified,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"evidence: {len(found)} referenced, {len(missing)} missing, {len(classified)} classified")
    if unclassified:
        print(f"unclassified missing paths ({len(unclassified)}):")
        for path in unclassified[:20]:
            print(f"  {path}")
    print(f"report: {report}")
    if unclassified:
        return 1
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
