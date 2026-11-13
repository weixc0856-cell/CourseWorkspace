from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from . import index as index_mod
from .bookmap import build as build_bookmap
from .bookmap import write as write_bookmap
from .evidence import EvidenceError, attach
from .extract import (
    ExtractorUnavailable,
    Extraction,
    extract_pdf,
    extract_text,
    load_page_texts,
    write_pages,
)
from .models import SourceMeta
from .qa import load_source, verify as verify_source
from .report import (
    analyse as analyse_extraction,
    parse_pages,
    write as write_extraction,
)
from .retrieve import RetrieveError, export_lesson, retrieve, write as write_retrieval
from .segment import SegmentError, build_units, load_units
from .spancheck import check as check_spans
from .spancheck import write as write_spancheck
from .toc import (
    TocError,
    load as load_toc,
    load_manual,
    resolve as resolve_toc,
    save as save_toc,
    write_page_map,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _root(source_id: str, root: Path | None) -> Path:
    return (root or Path("knowledge") / source_id).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_page_map(root: Path, records: list[PageRecord], offset: int = 0) -> Path:
    payload = {
        "schema_version": 1,
        "page_offset": offset,
        "pages": [
            record.model_dump(mode="json") | {
                "printed_page": (
                    record.pdf_page - offset
                    if offset and record.pdf_page - offset >= 1
                    else record.printed_page
                )
            }
            for record in records
        ],
    }
    target = root / "metadata" / "page_map.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def _import(extraction: Extraction, original: Path, root: Path, meta: dict) -> SourceMeta:
    root.mkdir(parents=True, exist_ok=True)
    records = write_pages(root, extraction)
    original_dir = root / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    target = original_dir / original.name
    shutil.copy2(original, target)
    source = SourceMeta(
        source_id=meta["source_id"],
        title=meta.get("title") or extraction.title or original.stem,
        authors=meta.get("authors") or [],
        edition=meta.get("edition"),
        publisher=meta.get("publisher"),
        year=meta.get("year"),
        isbn=meta.get("isbn"),
        language=meta.get("language"),
        kind=meta.get("kind") or "textbook",
        original=f"original/{original.name}",
        original_sha256=_sha_file(target),
        pdf_pages=len(extraction.pages),
        extractor=extraction.extractor,
        extracted_at=_now(),
    )
    (root / "source.yaml").write_text(
        yaml.safe_dump(source.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    write_page_map(root, records)
    return source


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.command("import-source")
def import_source_command(
    pdf: Path = typer.Option(..., "--pdf", exists=True, dir_okay=False),
    source_id: str = typer.Option(..., "--source-id"),
    root: Path | None = typer.Option(None, "--root"),
    title: str | None = typer.Option(None, "--title"),
    authors: str | None = typer.Option(None, "--authors", help="Comma separated."),
    edition: str | None = typer.Option(None, "--edition"),
    year: int | None = typer.Option(None, "--year"),
    language: str | None = typer.Option(None, "--language"),
) -> None:
    """Import a PDF into page files with a source manifest (local only)."""
    target = _root(source_id, root)
    try:
        extraction = extract_pdf(pdf.resolve())
    except ExtractorUnavailable as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    source = _import(
        extraction,
        pdf.resolve(),
        target,
        {
            "source_id": source_id,
            "title": title,
            "authors": [item.strip() for item in (authors or "").split(",") if item.strip()],
            "edition": edition,
            "year": year,
            "language": language,
        },
    )
    typer.echo(f"source: {source.source_id} pages: {source.pdf_pages} extractor: {source.extractor}")
    typer.echo(f"root: {target}")


@app.command("import-text")
def import_text_command(
    text: Path = typer.Option(..., "--text", exists=True, dir_okay=False),
    source_id: str = typer.Option(..., "--source-id"),
    root: Path | None = typer.Option(None, "--root"),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    """Import pre-extracted text (form feeds or `<!-- ks:page pdf=N -->`)."""
    target = _root(source_id, root)
    extraction = extract_text(text.resolve())
    source = _import(
        extraction, text.resolve(), target, {"source_id": source_id, "title": title}
    )
    typer.echo(f"source: {source.source_id} pages: {source.pdf_pages} extractor: {source.extractor}")


@app.command("toc")
def toc_command(
    root: Path = typer.Option(..., "--root"),
    scan_pages: int = typer.Option(12, "--scan-pages"),
    search: int = typer.Option(40, "--search", help="Offset search window in pages."),
    manual: Path | None = typer.Option(None, "--manual", exists=True, dir_okay=False),
) -> None:
    """Parse the TOC, calibrate printed→PDF pages and write page_map."""
    root = root.resolve()
    pages = load_page_texts(root)
    try:
        if manual is not None:
            entries = load_manual(manual)
            info = {"method": "manual", "page_offset": 0, "entries": len(entries)}
        else:
            entries, info = resolve_toc(pages, scan_pages=scan_pages, search=search)
    except TocError as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    save_toc(root, entries, info)
    offset = int(info.get("page_offset") or 0)
    write_page_map(root, offset=offset)
    typer.echo(f"method: {info['method']} entries: {len(entries)} offset: {offset}")
    for entry in entries[:12]:
        typer.echo(f"  L{entry.level} p{entry.printed_page} -> pdf {entry.pdf_page}  {entry.title}")


@app.command("segment")
def segment_command(
    root: Path = typer.Option(..., "--root"),
    max_units: int | None = typer.Option(None, "--max-units"),
) -> None:
    """Split the source into chapter units with page-marked files."""
    root = root.resolve()
    try:
        entries, _ = load_toc(root)
        units = build_units(root, entries, max_units=max_units)
    except (TocError, SegmentError) as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"units: {len(units)}")
    for unit in units:
        typer.echo(
            f"  {unit.unit_id} pdf {unit.pdf_pages[0]}-{unit.pdf_pages[1]} "
            f"figures {unit.figure_count}  {unit.title}"
        )


@app.command("index")
def index_command(
    root: Path = typer.Option(..., "--root"),
) -> None:
    """Rebuild the SQLite + FTS5 index for a source."""
    root = root.resolve()
    source = load_source(root)
    try:
        result = index_mod.build(root, source.source_id)
    except (index_mod.IndexError, SegmentError) as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"indexed pages: {result['pages']} units: {result['units']}")
    typer.echo(f"db: {result['db']}")


@app.command("retrieve")
def retrieve_command(
    root: Path = typer.Option(..., "--root"),
    query: str = typer.Option(..., "--query"),
    max_pages: int = typer.Option(18, "--max-pages"),
    excerpt_chars: int = typer.Option(700, "--excerpt-chars"),
    into_lesson: Path | None = typer.Option(None, "--into-lesson"),
    entry_id: str | None = typer.Option(None, "--entry-id", help="sources.yaml id, e.g. S14."),
) -> None:
    """Select the pages a lesson needs and write a citable retrieval artifact."""
    root = root.resolve()
    try:
        result = retrieve(root, query, max_pages=max_pages, excerpt_chars=excerpt_chars)
        paths = write_retrieval(root, result)
    except (RetrieveError, index_mod.IndexError) as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        f"{result.query_id}: {result.pages_read}/{result.total_pages} pages "
        f"({result.ratio * 100:.1f}%) units: {', '.join(result.units)}"
    )
    typer.echo(f"json: {paths['json']}")
    typer.echo(f"markdown: {paths['markdown']}")
    if into_lesson is not None:
        exported = export_lesson(
            root, result, into_lesson.resolve(), entry_id=entry_id
        )
        typer.echo(f"lesson source: {exported['source']}")
        typer.echo(f"sources fragment: {exported['fragment']}")


@app.command("evidence")
def evidence_command(
    root: Path = typer.Option(..., "--root"),
    retrieval: Path = typer.Option(..., "--retrieval", exists=True, dir_okay=False),
    claims: Path = typer.Option(..., "--claims", exists=True, dir_okay=False),
) -> None:
    """Attach claims to retrieved pages; verification stays pending."""
    try:
        target = attach(root.resolve(), retrieval.resolve(), claims.resolve())
    except EvidenceError as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"evidence: {target}")


@app.command("span-check")
def span_check_command(
    root: Path = typer.Option(..., "--root"),
    evidence: Path = typer.Option(..., "--evidence", exists=True, dir_okay=False),
    claims: Path | None = typer.Option(
        None, "--claims", exists=True, dir_okay=False, help="Optional quote source."
    ),
    strict_numbers: bool = typer.Option(
        False, "--strict-numbers", help="Treat missing numbers as blocking."
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Check that quoted spans and numbers exist on the cited pages."""
    root = root.resolve()
    try:
        report = check_spans(
            root,
            evidence.resolve(),
            claims_path=claims.resolve() if claims else None,
            strict_numbers=strict_numbers,
        )
    except Exception as exc:  # noqa: BLE001 - unreadable evidence blocks
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    paths = write_spancheck(root, report, evidence.resolve())
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(
            f"span-check: {report['status']} · claims {report['counts']['claims']} · "
            f"ok {report['counts']['ok']} · warnings {report['counts']['warnings']} · "
            f"blocking {report['counts']['blocking']}"
        )
        typer.echo(f"json: {paths['json']}")
        typer.echo(f"markdown: {paths['markdown']}")
    raise typer.Exit(0 if report["status"] in {"pass", "warn"} else 1)


@app.command("map")
def map_command(
    root: Path = typer.Option(..., "--root"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Write a deterministic chapter/page/unit map for the source."""
    root = root.resolve()
    try:
        report = build_bookmap(root)
    except Exception as exc:  # noqa: BLE001 - an unindexed source is a block
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    paths = write_bookmap(root, report)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(
            f"map: {len(report['chapters'])} chapters · "
            f"{report['units_total']} units · {report['pdf_pages']} pages"
        )
        typer.echo(f"json: {paths['json']}")
        typer.echo(f"markdown: {paths['markdown']}")
    raise typer.Exit(0)


@app.command("verify")
def verify_command(
    root: Path = typer.Option(..., "--root"),
) -> None:
    """Check that pages, units, citations and claims all resolve."""
    root = root.resolve()
    report = verify_source(root)
    for check in report["checks"]:
        typer.echo(f"[{check['id']}] {check['status']}: {check['detail']}")
    typer.echo(f"status: {report['status']}")
    raise typer.Exit(0 if report["status"] == "pass" else 1)


@app.command("extract-report")
def extract_report_command(
    root: Path = typer.Option(..., "--root"),
    min_chars: int = typer.Option(200, "--min-chars"),
    allow_empty: str = typer.Option(
        "", "--allow-empty", help="Known-blank PDF pages, e.g. 12,13-15."
    ),
    header_ratio: float = typer.Option(0.8, "--header-ratio"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Scan extracted pages for missing, blank or damaged text before indexing."""
    root = root.resolve()
    try:
        allowed = parse_pages(allow_empty)
    except ValueError as exc:
        typer.echo(f"blocked: bad --allow-empty: {exc}", err=True)
        raise typer.Exit(2)
    try:
        report = analyse_extraction(
            root,
            min_chars=min_chars,
            allow_empty=allowed,
            header_ratio=header_ratio,
        )
    except Exception as exc:  # noqa: BLE001 - any unreadable source is a block
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    paths = write_extraction(root, report)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
        raise typer.Exit(0 if report["status"] == "pass" else 1)
    else:
        counts = report["counts"]
        typer.echo(
            f"pages: {counts['page_files']}/{counts['pdf_pages']}  "
            f"median: {counts['chars_median']} chars  units: {counts['units']}"
        )
        for item in report["fatal"]:
            typer.echo(f"  [fatal] {item}")
        for item in report["serious"]:
            typer.echo(f"  [review] {item}")
        for item in report["cosmetic"][:5]:
            typer.echo(f"  [note] {item}")
        typer.echo(f"report: {paths['markdown']}")
        typer.echo(f"json:   {paths['json']}")
    typer.echo(f"status: {report['status']}")
    raise typer.Exit(0 if report["status"] == "pass" else 1)


@app.command("status")
def status_command(
    root: Path = typer.Option(..., "--root"),
) -> None:
    """Show what exists for a source without rebuilding anything."""
    root = root.resolve()
    try:
        source = load_source(root)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(1)
    pages = load_page_texts(root)
    units = load_units(root)
    retrievals = sorted((root / "retrieval").glob("*.json"))
    typer.echo(f"source: {source.source_id}  {source.title}")
    typer.echo(f"pages: {len(pages)}/{source.pdf_pages}  units: {len(units)}  retrievals: {len(retrievals)}")
    typer.echo(f"index: {'present' if index_mod.db_path(root).is_file() else 'missing'}")

@app.command("knowledge-ir-validate")
def knowledge_ir_validate_command(
    file: Path = typer.Option(..., "--file", help="knowledge-ir JSON/YAML"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Validate concepts, prerequisites and claim evidence sufficiency."""
    from .knowledge_ir import load_knowledge, validate_knowledge

    try:
        ir = load_knowledge(file)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    issues = validate_knowledge(ir)
    if as_json:
        typer.echo(json.dumps([item.model_dump() for item in issues], ensure_ascii=False, indent=2))
    else:
        typer.echo(f"concepts: {len(ir.concepts)}  claims: {len(ir.claims)}")
        for issue in issues:
            typer.echo(f"  [{issue.level}] {issue.code}: {issue.message}")
        typer.echo("errors: %d" % sum(1 for item in issues if item.level == "error"))
    raise typer.Exit(1 if any(item.level == "error" for item in issues) else 0)


@app.command("curriculum-validate")
def curriculum_validate_command(
    plan: Path = typer.Option(..., "--plan", help="curriculum YAML"),
    knowledge: Path = typer.Option(..., "--knowledge", help="knowledge-ir JSON/YAML"),
    min_lessons: int | None = typer.Option(None, "--min-lessons"),
    max_lessons: int | None = typer.Option(None, "--max-lessons"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Check coverage, prerequisite order and lesson count of a curriculum."""
    from .knowledge_ir import load_curriculum, load_knowledge, validate_curriculum

    try:
        ir = load_knowledge(knowledge)
        curriculum = load_curriculum(plan)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    issues = validate_curriculum(
        curriculum, ir, min_lessons=min_lessons, max_lessons=max_lessons
    )
    if as_json:
        typer.echo(json.dumps([item.model_dump() for item in issues], ensure_ascii=False, indent=2))
    else:
        typer.echo(f"lessons: {len(curriculum.lessons)}  concepts: {len(ir.concepts)}")
        for issue in issues:
            typer.echo(f"  [{issue.level}] {issue.code}: {issue.message}")
        typer.echo("errors: %d" % sum(1 for item in issues if item.level == "error"))
    raise typer.Exit(1 if any(item.level == "error" for item in issues) else 0)

@app.command("schemas")
def schemas_command(
    output: Path = typer.Option(Path("shared/schemas"), "--output"),
) -> None:
    """Export JSON Schema for the knowledge and curriculum contracts."""
    from .knowledge_ir import CurriculumPlan, KnowledgeIR

    output.mkdir(parents=True, exist_ok=True)
    for name, model in {"knowledge-ir": KnowledgeIR, "curriculum": CurriculumPlan}.items():
        target = output / f"{name}.schema.json"
        target.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + chr(10),
            encoding="utf-8",
        )
        typer.echo(f"wrote {target}")
