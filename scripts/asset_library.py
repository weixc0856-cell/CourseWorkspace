"""Query the local 3D asset library without re-downloading anything.

Usage:
    uv run --project CourseControl python scripts/asset_library.py --tag rock
    uv run --project CourseControl python scripts/asset_library.py --kind model --json
    uv run --project CourseControl python scripts/asset_library.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from course_control.platform.workspace_layout import content_root


def load_library(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"asset library not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise SystemExit(f"invalid asset library: {path}")
    return data


def matches(asset: dict, query: str | None, tags: list[str], kind: str | None, used_in: str | None) -> bool:
    if kind and asset.get("kind") != kind:
        return False
    if used_in and used_in not in (asset.get("used_in") or []):
        return False
    if tags:
        asset_tags = {str(item).lower() for item in (asset.get("tags") or [])}
        if not all(tag.lower() in asset_tags for tag in tags):
            return False
    if query:
        haystack = " ".join(
            str(asset.get(key) or "")
            for key in ("id", "name", "kind", "source")
        ) + " " + " ".join(str(item) for item in (asset.get("tags") or []))
        if query.lower() not in haystack.lower():
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the local 3D asset library.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--library", type=Path, default=None)
    parser.add_argument("--query", default=None, help="substring across id/name/tags")
    parser.add_argument("--tag", action="append", default=[], help="require this tag; repeatable")
    parser.add_argument("--kind", default=None, help="model, texture, hdri")
    parser.add_argument("--used-in", default=None, help="filter by project/lesson id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="verify every path exists")
    args = parser.parse_args()

    root = content_root(args.workspace.resolve())
    library_path = args.library or (root / "assets" / "3d" / "library.json")
    data = load_library(library_path)
    assets = [item for item in data["assets"] if isinstance(item, dict)]

    if args.check:
        missing = []
        for asset in assets:
            path = Path(str(asset.get("path") or ""))
            if not path.is_absolute():
                path = root / "assets" / "3d" / path
            if not path.exists():
                missing.append({"id": asset.get("id"), "path": str(path)})
        if missing:
            print(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False, indent=2))
            return 1
        print(f"asset library ok: {len(assets)} assets under {library_path}")
        return 0

    selected = [
        asset for asset in assets
        if matches(asset, args.query, args.tag, args.kind, args.used_in)
    ]
    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        print(f"{len(selected)} asset(s)")
        for asset in selected:
            dims = asset.get("dimensions_m")
            dim_text = " x ".join(f"{value:g}" for value in dims) + " m" if dims else ""
            print(
                f"  {asset.get('id')}  [{asset.get('kind')}/{asset.get('license')}]  "
                f"{asset.get('path')}"
                + (f"  ({dim_text})" if dim_text else "")
            )
            tags = ", ".join(asset.get("tags") or [])
            if tags:
                print(f"    tags: {tags}")
    return 0 if selected else 1


if __name__ == "__main__":
    sys.exit(main())
