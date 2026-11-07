"""Run the independent E6.5 multi-head calculation and write a JSON report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from multi_head_math import compute


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/manim-multi-head/e6.5/math-report.json"),
        help="where to write the JSON report",
    )
    args = parser.parse_args()

    report = compute()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
