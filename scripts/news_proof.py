"""Build the Remotion props for the news proof from the real timeline.

Tier and source are never retyped here: a card takes its tier from the text
suffix, and a footage entry takes both tier and attribution from the ledger
record it points at. That keeps the on-screen label tied to the same record the
contract validates.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CourseControl" / "src"))
from course_control.platform.workspace_layout import content_root  # noqa: E402

TIER = re.compile(r"\s*·\s*(DOCUMENTED|REPORTED|INFERENCE|CLAIM)\s*$")


def short(text: str, limit: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--staging-prefix", required=True)
    args = parser.parse_args()

    authoring = content_root(args.workspace) / "lessons" / args.slug / "authoring"
    timeline = yaml.safe_load((authoring / "timeline.yaml").read_text(encoding="utf-8"))
    ledger = yaml.safe_load((authoring / "ledger.yaml").read_text(encoding="utf-8"))
    assets = {r["asset_id"]: r for r in ledger.get("records", [])}

    entries = []
    for entry in timeline["entries"]:
        if entry["start_s"] >= args.seconds:
            break
        text = entry.get("text", "") or ""
        tier = ""
        match = TIER.search(text)
        if match:
            tier = match.group(1)
            text = TIER.sub("", text)

        item = {k: entry[k] for k in ("id", "kind", "start_s", "duration_s", "renderer") if k in entry}
        item["text"] = text
        item["source"] = entry.get("source", "") or ""

        asset_ids = entry.get("asset_ids") or []
        if asset_ids:
            asset = assets.get(asset_ids[0], {})
            tags = asset.get("tags") or []
            tier = tier or next((t.split(":", 1)[1] for t in tags if t.startswith("tier:")), "")
            # `attribution` is the on-screen English string; the ledger's `source`
            # is the research note and may be Chinese, which must not reach the frame.
            display = asset.get("attribution")
            if not display:
                publisher = asset.get("publisher") or ""
                title = short(asset.get("source") or "")
                display = " · ".join(x for x in (publisher, title) if x)
            item["source"] = display
            path = asset.get("path")
            item["image"] = (
                f"{args.staging_prefix}/{Path(path).name}" if path else None
            )
        item["tier"] = tier
        entries.append(item)

    payload = {"fps": 30, "duration_s": args.seconds, "entries": entries}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in entries:
        print(f"  {item['id']:<14} {item.get('renderer') or '-':<12} tier={item['tier'] or '-':<11} {item['source'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
