"""Render the golden set and compare it with the stored frames.

Every case names a composition, a frame and a golden image under the content
root. A case whose mean pixel difference exceeds its threshold is written to
the exception queue; the command exits 1 if any compared case fails.

Usage:
    uv run --project CourseControl python scripts/golden_check.py --workspace .
    uv run --project CourseControl python scripts/golden_check.py --no-render --only photo
    uv run --project CourseControl python scripts/golden_check.py --selftest
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from course_control.platform.workspace_layout import content_root


def mean_diff(golden: Path, current: Path) -> float:
    reference = Image.open(golden).convert("RGB")
    candidate = Image.open(current).convert("RGB")
    if candidate.size != reference.size:
        candidate = candidate.resize(reference.size)
    difference = ImageChops.difference(reference, candidate)
    channels = ImageStat.Stat(difference).mean
    return sum(channels) / (3 * 255)


def render_case(case: dict, composition: dict, studio: Path, out: Path) -> None:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node not found on PATH")
    cli = studio / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise SystemExit(f"remotion cli not found: {cli}")
    command = [
        node,
        str(cli),
        "still",
        composition["entry"],
        composition["id"],
        f"--frame={case['frame']}",
        f"--output={out}",
    ]
    result = subprocess.run(command, cwd=studio)
    if result.returncode != 0:
        raise SystemExit(f"render failed for {case['name']} (exit {result.returncode})")


def selftest(root: Path) -> int:
    folder = root / "selftest"
    folder.mkdir(parents=True, exist_ok=True)
    base = Image.new("RGB", (64, 64), (20, 20, 24))
    base.save(folder / "a.png")
    base.save(folder / "b.png")
    shifted = Image.new("RGB", (64, 64), (20, 20, 24))
    for x in range(32):
        for y in range(32):
            shifted.putpixel((x, y), (220, 120, 40))
    shifted.save(folder / "c.png")
    same = mean_diff(folder / "a.png", folder / "b.png")
    different = mean_diff(folder / "a.png", folder / "c.png")
    ok = same <= 0.02 < different
    print(f"identical: {same:.6f}  shifted: {different:.6f}  threshold 0.02")
    print("selftest: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path("RemotionStudio/golden/manifest.json"))
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    root = content_root(workspace)
    if args.selftest:
        return selftest(root / "build" / "golden")

    manifest_path = args.manifest if args.manifest.is_absolute() else workspace / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    composition = manifest["composition"]
    studio = workspace / "RemotionStudio"
    current_dir = root / "build" / "golden" / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in manifest["cases"]:
        if args.only and case["name"] not in args.only:
            continue
        current = current_dir / f"{case['name']}.png"
        golden = root / case["golden"] if case.get("golden") else None
        if not args.no_render:
            render_case(case, composition, studio, current)
        entry = {
            "name": case["name"],
            "component": case.get("component"),
            "frame": case.get("frame"),
            "golden": str(golden) if golden else None,
            "current": str(current),
            "threshold": case.get("threshold", 0.02),
        }
        if golden is None:
            entry.update({"status": "render_only", "diff": None})
        elif not golden.is_file():
            entry.update({"status": "fail", "diff": None, "detail": "golden missing"})
        elif not current.is_file():
            entry.update({"status": "not_run", "diff": None, "detail": "current frame missing"})
        else:
            diff = mean_diff(golden, current)
            entry.update({"status": "pass" if diff <= entry["threshold"] else "fail", "diff": round(diff, 6)})
        results.append(entry)
        print(f"  [{entry['status']}] {entry['name']} diff={entry['diff']} threshold={entry['threshold']}")

    report = {"schema_version": 1, "manifest": str(manifest_path), "results": results}
    report_path = root / "build" / "golden" / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [item for item in results if item["status"] == "fail"]
    exceptions = [item for item in results if item["status"] in {"fail", "not_run"}]
    (root / "build" / "golden" / "exceptions.json").write_text(
        json.dumps({"schema_version": 1, "exceptions": exceptions}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report: {report_path}")
    print(f"failures: {len(failures)} of {len(results)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
