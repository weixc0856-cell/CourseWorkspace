"""Course files belong in the content root, never in the program workspace.

The workspace holds the pipeline: code, schemas, fixtures, scripts and docs.
Course content -- lessons, engine scenes, render tasks, narration, media --
lives under the content root and is not committed here.

The rule is checked, not assumed: any directory named after a lesson inside the
workspace is reported.  Two exceptions exist and each carries its reason:

* fixtures the test suite owns (a lesson-shaped name, but test data);
* directory junctions, where only the path lives in the repository and the
  bytes do not.  Junctions are skipped, because the files are not stored here.

Two more detectors keep media out of the repository:

* a media file (image, video, audio, 3D asset, subtitle) anywhere in the
  workspace, unless its path carries an allowlist reason;
* a render-output directory name (out, output, frames, renders, captures) that
  holds media.

Neither detector consults .gitignore: an ignored file still sits on the disk,
still bloats every clone that copies it, and hides itself from git status
exactly when someone needs to notice it.
"""

from __future__ import annotations

import os
from pathlib import Path

from course_control.platform.workspace_layout import content_root, lessons_root

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

# Lesson-named paths that stay in the repository on purpose.
# Empty since 2026-11-12: the last three lesson-shaped directories became content-root
# paths behind junctions.  Add an entry only together with its reason.
ALLOWED: dict[str, str] = {
    "RemotionStudio/public/staging": "staging area for content-root media; the folder names match lesson slugs on purpose",
}

MEDIA_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp",
    ".mp4", ".mov",
    ".wav", ".m4a", ".mp3",
    ".glb", ".gltf", ".fbx", ".blend", ".exr", ".hdr",
    ".srt",
}

OUTPUT_DIR_NAMES = {"out", "output", "frames", "renders", "captures"}

# Staging is a cache: it may hold media, but it must not grow without bound.
STAGING_DIR = "RemotionStudio/public/staging"
STAGING_WARN_BYTES = 512 * 1024 * 1024
STAGING_LIMIT_BYTES = 2 * 1024 * 1024 * 1024

# Remotion writes a still to the current directory when no output path is
# given, and the file carries no extension. Sniff the header instead of relying
# on the name. Anything smaller than 64 KB is not worth probing.
SIGNATURE_MIN_BYTES = 64 * 1024


def _sniff_media(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(12)
    except OSError:
        return None
    if head.startswith(bytes.fromhex("89504e470d0a1a0a")):
        return "png"
    if head.startswith(bytes.fromhex("ffd8ff")):
        return "jpeg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    return None


# Media paths that stay in the repository on purpose.  Add an entry only
# together with its reason; episode media belongs in the content root and
# reaches Remotion through public/staging/<slug>/.
MEDIA_ALLOWED: dict[str, str] = {
    "BlenderStudio/assets/geometry_nodes": "Blender asset library shipped with the geometry-node demo",
    "BlenderStudio/scenes/lesson-blender-only": "test fixture scene for the Blender runner",
    "BlenderStudio/scenes/lesson-smoke": "test fixture scene for the Blender runner",
    "BrandIntro/gates/evidence-2026-11-10": "committed brand-intro gate evidence (four frames)",
    "CodeVideoStudio/backends/hyperframes/hf-poc/out": "hyperframes POC output cited by docs/ACCEPTANCE.md; move to the content root by 2026-12-15",
    "CourseControl/tests/fixtures": "test fixtures",
    "ModelingStudio/tests/fixtures": "test fixtures",
    "ModelingStudio/workspace": "ModelingStudio job workspace (runtime); migrate to the content root by 2026-12-15",
    "RemotionStudio/public/fengshui": "legacy media for the fengshui episode; content-root copy exists under projects/fengshui; owner decides removal by 2026-12-15",
    "RemotionStudio/public/fengshui-ab": "legacy media for the fengshui A/B experiment; content-root copy exists under projects/fengshui/experiments; owner decides removal by 2026-12-15",
    "RemotionStudio/public/opener": "brand-opener audio; no content-root source found yet; owner decides keep or regenerate by 2026-12-15",
    "RemotionStudio/public/audit-fixtures": "committed fixtures for the frame-audit code regression; never lesson content",
    "RemotionStudio/public/staging": "staging area copied from the content root by scripts/stage-media.mjs",
    "RemotionStudio/public/vibe": "legacy music for the vibe compositions; content-root copy exists under projects/experiments; owner decides removal by 2026-12-15",
    "ScientificFigures/output": "figure output cited by the POC evaluation doc; move to the content root by 2026-12-15",
}


# Prose and contracts belong in docs/; anything else there is project material or a
# stray artefact.  Reported as a warning: a deliberate diagram is fine, a video is not.
# Logs are runtime noise (a stray browser can drop one anywhere), never a
# document; they are gitignored anyway.
DOC_PROSE_SUFFIXES = {".md", ".yaml", ".yml", ".log"}
DOC_PROGRAM_PATHS = ("docs/contracts/",)


def docs_data_files(workspace: Path) -> list[str]:
    docs = Path(workspace).resolve() / "docs"
    if not docs.is_dir():
        return []
    found: list[str] = []
    for path in sorted(docs.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(Path(workspace).resolve()).as_posix()
        if path.suffix.lower() in DOC_PROSE_SUFFIXES:
            continue
        if relative.startswith(DOC_PROGRAM_PATHS):
            continue
        found.append(relative)
    return found


def audit(workspace: Path) -> dict:
    workspace = Path(workspace).resolve()
    root = content_root(workspace)
    if root == workspace:
        return {
            "configured": False,
            "content_root": str(root),
            "entries": [],
            "problems": [],
            "media": [],
            "media_problems": [],
            "output_dir_problems": [],
            "docs_data": [],
            "note": "内容根等于工作区：课程文件本来就在程序目录里，未启用分离检查。",
        }

    lessons = lessons_root(workspace)
    slugs = {item.name for item in lessons.iterdir() if item.is_dir()} if lessons.is_dir() else set()
    entries: list[dict] = []
    media: list[dict] = []
    output_dirs: set[str] = set()
    staging_bytes = 0
    staging_slugs: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(workspace):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            candidate = current / name
            if os.path.isjunction(candidate) or os.path.islink(candidate):
                continue  # the path is a link; the bytes live in the content root
            kept.append(name)
        dirnames[:] = kept
        relative_dir = current.relative_to(workspace).as_posix()
        if current != workspace and current.name.lower() in OUTPUT_DIR_NAMES:
            output_dirs.add(relative_dir)
        if current.name in slugs:
            reason = _allowed(relative_dir)
            entries.append(
                {
                    "path": relative_dir,
                    "slug": current.name,
                    "allowed": reason is not None,
                    "reason": reason,
                }
            )
        for name in filenames:
            suffix = Path(name).suffix.lower()
            if suffix not in MEDIA_SUFFIXES:
                try:
                    size = (current / name).stat().st_size
                except OSError:
                    continue
                if size < SIGNATURE_MIN_BYTES or _sniff_media(current / name) is None:
                    continue
            else:
                try:
                    size = (current / name).stat().st_size
                except OSError:
                    size = 0
            relative = name if relative_dir == "." else relative_dir + "/" + name
            reason = _media_allowed(relative)
            media.append({"path": relative, "allowed": reason is not None, "reason": reason})
            if relative.startswith(STAGING_DIR + "/"):
                staging_bytes += size
                slug = relative[len(STAGING_DIR) + 1:].split("/")[0]
                staging_slugs[slug] = staging_slugs.get(slug, 0) + size

    problems = [entry["path"] for entry in entries if not entry["allowed"]]
    media_problems = [item["path"] for item in media if not item["allowed"]]
    staging_problem = None
    if staging_bytes > STAGING_LIMIT_BYTES:
        staging_problem = (
            f"{STAGING_DIR}: {staging_bytes} bytes exceeds the {STAGING_LIMIT_BYTES}-byte limit"
        )
    staging_warning = None
    if staging_bytes > STAGING_WARN_BYTES and staging_problem is None:
        staging_warning = (
            f"{STAGING_DIR}: {staging_bytes} bytes is above the {STAGING_WARN_BYTES}-byte warning line"
        )
    output_dir_problems = sorted(
        relative
        for relative in output_dirs
        if _media_allowed(relative) is None
        and any(item["path"].startswith(relative + "/") for item in media)
    )
    return {
        "configured": True,
        "content_root": str(root),
        "lessons": len(slugs),
        "entries": sorted(entries, key=lambda item: item["path"]),
        "problems": problems + media_problems + output_dir_problems
        + ([staging_problem] if staging_problem else []),
        "media": sorted(media, key=lambda item: item["path"]),
        "media_problems": media_problems,
        "output_dir_problems": output_dir_problems,
        "staging_bytes": staging_bytes,
        "staging_warn_bytes": STAGING_WARN_BYTES,
        "staging_limit_bytes": STAGING_LIMIT_BYTES,
        "staging_problem": staging_problem,
        "staging_warning": staging_warning,
        "staging_slugs": sorted(
            staging_slugs.items(), key=lambda item: item[1], reverse=True
        ),
        "docs_data": docs_data_files(workspace),
        "note": None,
    }


def _allowed(relative: str) -> str | None:
    return _match(ALLOWED, relative)


def _media_allowed(relative: str) -> str | None:
    return _match(MEDIA_ALLOWED, relative)


def _match(table: dict[str, str], relative: str) -> str | None:
    for path, reason in table.items():
        if relative == path or relative.startswith(path + "/"):
            return reason
    return None
