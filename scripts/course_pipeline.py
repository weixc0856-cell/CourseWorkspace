"""Unified production and maintenance CLI for CourseWorkspace and Content Root.

Mirrors the industrial physical separation architecture:
- Code Workspace (./ -> Git Remote)
- Content Root   (Resolved via config/local-paths.yaml or ./content_data)

Usage:
  python scripts/course_pipeline.py status
  python scripts/course_pipeline.py sync [--course automotive-aerodynamics] [--all]
  python scripts/course_pipeline.py clean-build [--course automotive-aerodynamics]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import yaml

from scripts.resolve_paths import (
    check_and_ensure_junction,
    get_content_root,
    get_course_map_path,
    get_episodes_dir,
    get_project_yaml_path,
    get_workspace_root,
)
from scripts.sync_episode_cards import sync_cards


def cmd_status(args: argparse.Namespace) -> None:
    workspace = get_workspace_root()
    content_root = get_content_root(workspace)

    print("================================================================================")
    print(" Course Production Pipeline Status (Dual-Root Physical Separation Architecture) ")
    print("================================================================================")

    # 1. Roots & Junction
    print(f"\n[1. Workspace & Content Roots]")
    print(f"  • Code Workspace (Git Repo) : {workspace}")
    print(f"  • Content Root (Media/Data) : {content_root} {'[OK]' if content_root.exists() else '[NOT FOUND]'}")

    junction_ok, junction_msg = check_and_ensure_junction(workspace)
    print(f"  • Directory Junction        : {'[OK]' if junction_ok else '[WARN]'} {junction_msg}")

    # Multi-root workspace file
    workspace_file = workspace / "CourseStudio.code-workspace"
    print(f"  • Multi-root Workspace File : {'[OK]' if workspace_file.exists() else '[MISSING]'} {workspace_file.name}")

    # 2. Course Project Status
    course_id = args.course
    print(f"\n[2. Course Project: {course_id}]")
    proj_yaml = get_project_yaml_path(course_id, workspace)
    if proj_yaml.exists():
        try:
            data = yaml.safe_load(proj_yaml.read_text(encoding="utf-8")) or {}
            course_cfg = data.get("production", {}).get("course", {})
            target_eps = course_cfg.get("lesson_count", {}).get("target", "N/A")
            sec_range = course_cfg.get("lesson_seconds", {})
            print(f"  • project.yaml              : [OK] (Target: {target_eps} episodes, Duration: {sec_range.get('min', 0)}s–{sec_range.get('max', 0)}s)")
        except Exception as e:
            print(f"  • project.yaml              : [ERROR reading: {e}]")
    else:
        print(f"  • project.yaml              : [NOT FOUND at {proj_yaml}]")

    # COURSE_MAP.md check
    course_map = get_course_map_path(course_id, workspace)
    if course_map.exists():
        map_text = course_map.read_text(encoding="utf-8")
        rows = [line for line in map_text.splitlines() if line.strip().startswith("|") and re_is_episode_row(line)]
        print(f"  • COURSE_MAP.md             : [OK] ({len(rows)} verified episodes)")
    else:
        rows = []
        print(f"  • COURSE_MAP.md             : [NOT FOUND at {course_map}]")

    # Episodes card directory
    episodes_dir = get_episodes_dir(course_id, workspace)
    if episodes_dir.exists():
        cards = list(episodes_dir.glob("*/card.yaml"))
        print(f"  • Episode Cards (card.yaml) : [OK] ({len(cards)} active slots)")
        if len(rows) > 0 and len(cards) < len(rows):
            print(f"    ↳ Notice: {len(rows) - len(cards)} episodes in map do not have cards yet. Run `python scripts/course_pipeline.py sync`.")
    else:
        print(f"  • Episode Cards             : [NOT FOUND at {episodes_dir}]")

    # 3. Git Boundary & Large File Security Audit
    print(f"\n[3. Git Isolation & Large File Security Audit]")
    try:
        git_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
        )
        staged_or_untracked = git_res.stdout.splitlines()
        forbidden_media_exts = {".mp4", ".mov", ".wav", ".mp3", ".gguf", ".safetensors", ".blend1"}
        leaked_media = [line for line in staged_or_untracked if any(line.endswith(ext) for ext in forbidden_media_exts)]
        leaked_content = [line for line in staged_or_untracked if "content_data" in line]

        if not leaked_media and not leaked_content:
            print(f"  • Large File Leak Guard     : [PASS] Zero media or content_data files tracked by Git.")
        else:
            if leaked_media:
                print(f"  • Large File Leak Guard     : [FAIL] Leaked media files detected: {leaked_media}")
            if leaked_content:
                print(f"  • Junction Leak Guard       : [FAIL] content_data is leaking into Git!")
        print(f"  • Git Working Tree State    : {len(staged_or_untracked)} pending items.")
    except Exception as e:
        print(f"  • Git Audit                 : [WARN] Git check error: {e}")

    # 4. Storage & Build Directory Footprint
    print(f"\n[4. Content Storage Footprint]")
    build_dir = content_root / "build"
    deliver_dir = content_root / "deliver"
    if build_dir.exists():
        build_mb = sum(f.stat().st_size for f in build_dir.rglob("*") if f.is_file()) / (1024 * 1024)
        print(f"  • build/ (Intermediate)     : {build_mb:.1f} MB (reconstructible cache)")
    if deliver_dir.exists():
        deliver_mb = sum(f.stat().st_size for f in deliver_dir.rglob("*") if f.is_file()) / (1024 * 1024)
        print(f"  • deliver/ (Final Masters)  : {deliver_mb:.1f} MB (permanent deliverables)")

    print("\n================================================================================")


def re_is_episode_row(line: str) -> bool:
    import re
    return bool(re.match(r"^\|\s*T\d+-\d{2}\s*\|", line))


def cmd_sync(args: argparse.Namespace) -> None:
    course_id = args.course
    modules = None if args.all or not args.modules else [m.strip().upper() for m in args.modules.split(",")]
    scope_str = "ALL 180 episodes" if modules is None else f"modules {modules}"
    print(f"Synchronizing episode cards with COURSE_MAP.md for course: {course_id} ({scope_str})...")
    sync_cards(course_id, modules=modules)
    print("Sync completed successfully.")


def cmd_clean_build(args: argparse.Namespace) -> None:
    content_root = get_content_root()
    build_dir = content_root / "build"
    if not build_dir.exists():
        print(f"build directory does not exist at {build_dir}")
        return

    print(f"Cleaning intermediate build cache at {build_dir}...")
    # Clean engine caches and logs while keeping directory skeleton
    targets = ["_engine-cache", "_logs", "_shared/tmp"]
    for t in targets:
        target_path = build_dir / t
        if target_path.exists():
            print(f"  Removing: {target_path}")
            shutil.rmtree(target_path, ignore_errors=True)
            target_path.mkdir(parents=True, exist_ok=True)
    print("Build cleanup completed successfully. (deliver/ and source files are untouched).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Course Production Pipeline CLI")
    parser.add_argument("--course", default="automotive-aerodynamics", help="Course ID")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Inspect pipeline, junction, git isolation and course status")
    sync_parser = subparsers.add_parser("sync", help="Synchronize COURSE_MAP.md to episode cards")
    sync_parser.add_argument("--modules", default=None, help="Comma-separated module IDs to sync (e.g. T1,T2,T3,T4). If omitted or with --all, syncs all.")
    sync_parser.add_argument("--all", action="store_true", help="Sync all 180 episodes across all modules")
    subparsers.add_parser("clean-build", help="Clean reconstructible intermediate build artifacts")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        cmd_status(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "clean-build":
        cmd_clean_build(args)


if __name__ == "__main__":
    main()
