"""Synchronize episode cards in CourseContent with COURSE_MAP.md (v5.2-Freeze).

Aligns:
- T1 (T1-01 to T1-05)
- T2 (T2-01 to T2-19)
- T3 (T3-01 to T3-06)
- T4 (T4-01 to T4-38)
Cleans up obsolete episode folders (e.g., T1-06..11, T3-07).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
import sys
import yaml

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.resolve_paths import (
    get_content_root,
    get_course_map_path,
    get_episodes_dir,
)


def sync_cards(course_id: str = "automotive-aerodynamics", modules: list[str] | None = None):
    content_root = get_content_root()
    course_map_path = get_course_map_path(course_id)
    episodes_dir = get_episodes_dir(course_id)
    archive_dir = content_root / "archive" / "obsolete_episodes"
    archive_dir.mkdir(parents=True, exist_ok=True)

    text = course_map_path.read_text(encoding="utf-8")
    row_pattern = re.compile(
        r"^\|\s*(T\d+-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*min\s*\|\s*(.*?)\s*\|$",
        re.M,
    )

    valid_episodes = {}
    for m in row_pattern.finditer(text):
        ep = m.group(1).strip()
        title = m.group(2).strip()
        sec = m.group(3).strip()
        page_str = m.group(4).strip()
        source = m.group(5).strip().strip("`")
        minutes = int(m.group(6).strip())
        summary = m.group(7).strip()
        valid_episodes[ep] = {
            "episode": ep,
            "title": title,
            "section": sec,
            "page": page_str,
            "source": source,
            "target_seconds": minutes * 60,
            "summary": summary,
        }

    print(f"Total valid episodes in map: {len(valid_episodes)}")

    # Check existing directories in episodes_dir
    existing_dirs = [d for d in episodes_dir.iterdir() if d.is_dir() and re.match(r"^T\d+-\d{2}$", d.name)]
    
    # 1. Archive obsolete episodes
    for d in existing_dirs:
        ep = d.name
        prefix = ep.split("-")[0]
        if (modules is None or prefix in modules) and ep not in valid_episodes:
            print(f"Archiving obsolete episode: {ep}")
            target_dst = archive_dir / ep
            if target_dst.exists():
                shutil.rmtree(target_dst)
            shutil.move(str(d), str(target_dst))

    # 2. Update or create card.yaml for valid episodes
    created_count = 0
    for ep, data in valid_episodes.items():
        prefix = ep.split("-")[0]
        if modules is not None and prefix not in modules:
            continue

        clean_title = data["title"].replace("**", "").strip()

        ep_dir = episodes_dir / ep
        ep_dir.mkdir(parents=True, exist_ok=True)
        card_file = ep_dir / "card.yaml"

        card_data = {}
        if card_file.exists():
            try:
                card_data = yaml.safe_load(card_file.read_text(encoding="utf-8")) or {}
            except Exception:
                card_data = {}

        card_data["schema_version"] = 1
        card_data["episode"] = ep
        if "slug" not in card_data:
            card_data["slug"] = f"{ep.lower()}-{re.sub(r'[^a-z0-9]+', '-', clean_title.lower()).strip('-')}"
        card_data["title"] = clean_title
        card_data["section"] = data["section"]
        card_data["target_seconds"] = data["target_seconds"]
        if "core_question" not in card_data or not card_data["core_question"]:
            card_data["core_question"] = data["summary"]
        if "concepts" not in card_data or not card_data["concepts"]:
            card_data["concepts"] = [data["section"]]
        if "claims" not in card_data:
            card_data["claims"] = []
        if "figures" not in card_data:
            card_data["figures"] = []
        if "borrow_from" not in card_data:
            card_data["borrow_from"] = []
        if "prerequisites" not in card_data:
            card_data["prerequisites"] = []
        if "cut_list" not in card_data:
            card_data["cut_list"] = ["Scope delimited to current section and core question."]
        card_data["status"] = "card"

        card_file.write_text(yaml.safe_dump(card_data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        created_count += 1

    print(f"Card synchronization completed: {created_count} cards active.")


if __name__ == "__main__":
    sync_cards()
