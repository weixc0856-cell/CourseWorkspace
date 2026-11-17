"""Fetch original book figures into a lesson's staging area.

Any Docling source follows the same layout under ``DOCLING_OUTPUT_ROOT``
(``config/local-paths.yaml`` ``docling_root`` + ``/output``):

    catalog.json              every source (documents, videos), id -> files
    <source_id>/
        assets/               one PNG per picture
        document.json         each picture carries caption and page_no
        manifest.json         the bundle's own file map
        document.md           images in body order (the reliable asset join)

The script never names a book.  It resolves ``--source-id`` through the
catalog, reads the bundle's own manifest for file locations, and copies the
original figures; it never redraws or re-encodes them.

Usage:
    uv run --project CourseControl python scripts/fetch_book_figures.py --list
    uv run --project CourseControl python scripts/fetch_book_figures.py \
        --lesson <slug> --source-id <source_id> --figure 1.67 --figure 3.9
    uv run --project CourseControl python scripts/fetch_book_figures.py \
        --lesson <slug> --source-id information-rules --page 181
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from course_control.platform.workspace_layout import content_root

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FIGURE_RE = re.compile(r"(?i)fig(?:ure)?\.?\s*([0-9]+[.\-][0-9]+)")

# 写入门禁：默认根不用 Path.cwd()，避免在任意目录运行时把图写进别人的内容根。
REPO_ROOT = Path(__file__).resolve().parents[1]


class SourceError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docling_root(workspace: Path) -> Path:
    """Resolve DOCLING_OUTPUT_ROOT from the local config, without guessing."""
    config = workspace / "config" / "local-paths.yaml"
    if config.is_file():
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        value = data.get("docling_root")
        if value:
            base = Path(str(value)).expanduser()
            if not base.is_absolute():
                base = workspace / base
            return (base / "output").resolve()
    raise SourceError(
        "cannot resolve DOCLING_OUTPUT_ROOT: set docling_root in config/local-paths.yaml "
        "or pass --docling-root"
    )


def load_catalog(root: Path) -> dict:
    path = root / "catalog.json"
    if not path.is_file():
        raise SourceError(f"catalog not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise SourceError(f"catalog has no sources: {path}")
    return sources


def resolve_source(sources: dict, source_id: str) -> dict:
    for key, entry in sources.items():
        if entry.get("source_id") == source_id or key == source_id or key.endswith(f":{source_id}"):
            return entry
    known = sorted({str(entry.get("source_id") or key) for key, entry in sources.items()})
    raise SourceError(
        f"source_id {source_id!r} is not in the catalog. Available: " + ", ".join(known)
    )


def bundle_dir(root: Path, entry: dict) -> Path:
    """Locate the bundle from its own manifest path; never infer the layout."""
    relative = (entry.get("files") or {}).get("manifest")
    candidates = []
    if relative:
        candidates.append((root.parent / relative).resolve())
        candidates.append((root / Path(relative).parent.name).resolve())
    candidates.append((root / str(entry.get("source_id"))).resolve())
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate
    raise SourceError(f"bundle directory not found for manifest {relative!r}")


def load_bundle(bundle: Path) -> tuple[list[dict], Path, Path]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    document_path = bundle / (files.get("docling_json") or "document.json")
    assets_dir = bundle / (files.get("assets") or "assets")
    markdown_path = bundle / (files.get("markdown") or "document.md")
    for label, path in (("document", document_path), ("assets", assets_dir), ("markdown", markdown_path)):
        if not path.exists():
            raise SourceError(f"bundle is missing {label}: {path}")
    document = json.loads(document_path.read_text(encoding="utf-8"))
    pictures = document.get("pictures") or []
    texts = document.get("texts") or []
    assets = []
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"!\[[^\]]*\]\((assets/[^)]+)\)", line)
        if match:
            assets.append(match.group(1))
    if len(assets) != len(pictures):
        raise SourceError(
            f"{bundle.name}: markdown lists {len(assets)} images but document.json has "
            f"{len(pictures)} pictures; the asset join cannot be built for this source"
        )
    records = []
    for index, (picture, asset) in enumerate(zip(pictures, assets)):
        captions = []
        for ref in picture.get("captions") or []:
            target = str(ref.get("$ref") or "")
            if not target.startswith("#/texts/"):
                continue
            try:
                item = texts[int(target.rsplit("/", 1)[1])]
            except (ValueError, IndexError):
                continue
            caption = str(item.get("text") or item.get("orig") or "").strip()
            if caption:
                captions.append(caption)
        caption = " ".join(captions)
        match = FIGURE_RE.search(caption)
        records.append(
            {
                "index": index,
                "page": int((picture.get("prov") or [{}])[0].get("page_no") or 0),
                "caption": caption,
                "figure": match.group(1).replace("-", ".") if match else None,
                "asset": asset,
                "bbox": (picture.get("prov") or [{}])[0].get("bbox"),
                "width": (picture.get("image") or {}).get("size", {}).get("width"),
                "height": (picture.get("image") or {}).get("size", {}).get("height"),
            }
        )
    return records, document_path, assets_dir


def parse_ref(spec: str) -> dict:
    ref: dict = {}
    for part in spec.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise SourceError(f"ref must be key=value: {part!r}")
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if key not in {"page", "caption", "chapter", "figure", "index"}:
            raise SourceError(f"unknown ref key: {key}")
        ref[key] = value.strip()
    if not ref:
        raise SourceError(f"empty ref: {spec!r}")
    for key in ("page", "chapter", "index"):
        if key in ref:
            try:
                ref[key] = int(ref[key])
            except ValueError:
                raise SourceError(f"{key} must be a number: {ref[key]!r}") from None
    return ref


def matches(record: dict, ref: dict) -> bool:
    if "index" in ref and record["index"] != ref["index"]:
        return False
    if "page" in ref and record["page"] != ref["page"]:
        return False
    caption = record["caption"].lower()
    if "caption" in ref and str(ref["caption"]).lower() not in caption:
        return False
    if "figure" in ref:
        if (record["figure"] or "").lower() != str(ref["figure"]).replace("-", ".").lower():
            return False
    if "chapter" in ref and not caption.startswith(f"figure {ref['chapter']}.".lower()):
        return False
    return True


def safe_name(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "-", value).strip("-") or "figure"


def _refs(args) -> list[str]:
    specs = [f"figure={item}" for item in args.figure]
    specs += [f"page={item}" for item in args.page]
    specs += [f"caption={item}" for item in args.caption]
    if args.refs:
        payload = yaml.safe_load(args.refs.read_text(encoding="utf-8")) or []
        if isinstance(payload, dict):
            payload = payload.get("refs") or []
        for item in payload:
            if isinstance(item, str):
                specs.append(item)
            elif isinstance(item, dict):
                specs.append(",".join(f"{key}={value}" for key, value in item.items()))
    return specs


class PathGuardError(RuntimeError):
    """Raised when a write target is outside the allowed roots."""


def _is_reparse(path: Path) -> bool:
    """True for symlinks and Windows junctions (both redirect a write)."""
    try:
        if path.is_symlink():
            return True
        if hasattr(path, "is_junction") and path.is_junction():
            return True
        attrs = path.lstat().st_file_attributes
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except (OSError, AttributeError):
        return False


def _lexical_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def guard_destination(workspace: Path, base_out: Path) -> Path:
    """Fail closed unless the write target sits in an allowed root.

    Allowed roots are the workspace and its configured content root.  Every
    component between the matching root and the target must be a real
    directory: a junction or symlink anywhere on that path is refused, because
    resolving it would write somewhere the caller never named.
    """
    workspace = Path(workspace).resolve()
    roots = [workspace]
    configured = content_root(workspace)
    if configured.resolve() != workspace:
        roots.append(configured.resolve())

    target = Path(base_out).resolve()
    root = next((candidate for candidate in roots if _lexical_under(target, candidate)), None)
    if root is None:
        raise PathGuardError(
            f"refusing to write outside the workspace and its content root: {target}"
        )

    # 用未解析的路径检查：resolve() 会把 junction 摊平，检查就失效了。
    # 先查 base_out 自身，再逐级查祖先——目标本身是链接时，只要它指向允许根内，
    # 范围检查就拦不住，必须显式拒绝。
    raw = Path(os.path.abspath(base_out))
    if os.path.lexists(raw) and _is_reparse(raw):
        raise PathGuardError(f"refusing to write through a link: {raw}")
    for candidate in raw.parents:
        if candidate.exists() and _is_reparse(candidate):
            raise PathGuardError(f"refusing to write through a link: {candidate}")

    if os.environ.get("COURSEWORKSPACE_MODE", "").strip().lower() == "dev":
        dev_root = os.environ.get("COURSEWORKSPACE_DEV_ROOT")
        if not dev_root:
            raise PathGuardError(
                "dev mode needs COURSEWORKSPACE_DEV_ROOT; refusing to guess a write root"
            )
        resolved_dev = Path(dev_root).expanduser().resolve()
        if not _lexical_under(target, resolved_dev):
            raise PathGuardError(
                f"dev mode refuses to write outside {resolved_dev}: {target}"
            )
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lesson", help="lesson slug; required unless --list")
    parser.add_argument("--source-id", help="Docling source id from catalog.json")
    parser.add_argument("--docling-root", type=Path, help="DOCLING_OUTPUT_ROOT (default from config)")
    parser.add_argument("--workspace", type=Path, help="course workspace (required when writing)")
    parser.add_argument("--out", type=Path, help="default: lessons/<lesson>/staging/ref_figs")
    parser.add_argument("--figure", action="append", default=[])
    parser.add_argument("--page", action="append", type=int, default=[])
    parser.add_argument("--caption", action="append", default=[])
    parser.add_argument("--refs", type=Path)
    parser.add_argument("--list", action="store_true", help="list catalog sources and exit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    explicit_workspace = args.workspace is not None
    workspace = (args.workspace or REPO_ROOT).resolve()

    writing = not args.dry_run and not args.list
    if writing and not explicit_workspace:
        print(
            "error: --workspace is required when writing figures; "
            "give the course workspace explicitly, or use --dry-run",
            file=sys.stderr,
        )
        return 2

    root = (args.docling_root or docling_root(workspace)).resolve()
    sources = load_catalog(root)
    if args.list:
        for key, entry in sorted(sources.items()):
            print(f"{entry.get('source_id')}\t{entry.get('kind')}\t{entry.get('title')}")
        return 0
    if not args.lesson or not args.source_id:
        raise SystemExit("--lesson and --source-id are required (use --list to see sources)")

    entry = resolve_source(sources, args.source_id)
    bundle = bundle_dir(root, entry)
    records, document_path, assets_dir = load_bundle(bundle)

    specs = _refs(args)
    if not specs:
        raise SystemExit("give at least one --figure / --page / --caption / --refs")
    refs = [parse_ref(spec) for spec in specs]
    selected = []
    failures = []
    for ref in refs:
        hits = [record for record in records if matches(record, ref)]
        if not hits:
            failures.append(ref)
        for record in hits:
            selected.append((ref, record))
    if failures:
        for ref in failures:
            print(f"no figure matched {ref} in {args.source_id}")
            page = ref.get("page")
            if page:
                for caption in [r["caption"] for r in records if r["page"] == page and r["caption"]][:5]:
                    print(f"  page {page}: {caption[:100]}")
        return 1

    base_out = args.out or (
        content_root(workspace) / "lessons" / args.lesson / "staging" / "ref_figs"
    )
    try:
        base_out = guard_destination(workspace, base_out)
    except PathGuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = base_out / args.source_id
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
    index_path = base_out / "index.json"
    previous: dict = {}
    if index_path.is_file():
        try:
            previous = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    entries = list(previous.get("figures") or [])
    seen = {(item.get("source_id"), item.get("file")) for item in entries}
    added = 0
    for ref, record in selected:
        asset = (bundle / record["asset"]).resolve()
        if not asset.is_file():
            print(f"asset missing on disk: {asset}")
            return 1
        figure_id = record["figure"] or f"p{record['page']}-i{record['index']}"
        name = f"fig-{safe_name(figure_id)}.png"
        suffix = 2
        while (args.source_id, name) in seen:
            name = f"fig-{safe_name(figure_id)}-{suffix}.png"
            suffix += 1
        seen.add((args.source_id, name))
        item = {
            "source_id": args.source_id,
            "figure_id": figure_id,
            "page": record["page"],
            "caption": record["caption"],
            "asset": str(asset),
            "file": f"{args.source_id}/{name}",
            "picture_index": record["index"],
            "bbox": record["bbox"],
            "width": record["width"],
            "height": record["height"],
            "match": ref,
        }
        if args.dry_run:
            print(f"[dry-run] {figure_id} p{record['page']} -> {out / name}")
            continue
        shutil.copyfile(asset, out / name)
        entries.append(item)
        added += 1
        print(f"{args.source_id} {figure_id} p{record['page']} -> {out / name}")
        if record["caption"]:
            print(f"  {record['caption'][:110]}")

    if args.dry_run:
        return 0

    source_meta = dict(previous.get("sources") or {})
    source_meta[args.source_id] = {
        "title": entry.get("title"),
        "kind": entry.get("kind"),
        "bundle": str(bundle),
        "document_sha256": _sha256(document_path),
    }
    index = {
        "schema_version": 1,
        "kind": "book_figure_refs",
        "lesson": args.lesson,
        "generated_at": _now(),
        "docling_root": str(root),
        "sources": source_meta,
        "note": "original figures copied as extracted; no redraw, no re-encode",
        "page_kind": "pdf page_no from the Docling extraction, not the printed page",
        "figures": entries,
    }
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"index: {index_path} ({len(entries)} entries, {added} added)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
