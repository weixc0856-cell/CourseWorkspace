from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from course_control.production.episode_spec import (
    EpisodeSpec,
    EpisodeSpecError,
    load_episode_spec,
)
from course_control.production.quality_rubric import (
    QualityRubricError,
    load_quality_rubric,
)

PAGE_PART = re.compile(r"^page:(\d+)(?:-(\d+))?$")
SHOT_PART = re.compile(r"^shot:(\S+)$")
BUDGET_RE = re.compile(
    r"时长预算\**\s*[：:]\s*([0-9]+(?:\.[0-9]+)?)\s*(秒|s|分钟|min)", re.I
)


@dataclass
class PreflightReport:
    lesson: str
    spec: EpisodeSpec | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _page_count(slides_path: Path) -> int | None:
    try:
        text = slides_path.read_text(encoding="utf-8")
    except OSError:
        return None
    return sum(1 for line in text.splitlines() if line.strip() == "---") + 1


def _shot_ids(storyboard_path: Path) -> set[str] | None:
    try:
        import yaml

        data = yaml.safe_load(storyboard_path.read_text(encoding="utf-8")) or {}
    except (OSError, Exception):  # noqa: BLE001 - a missing board is reported elsewhere
        return None
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list):
        return None
    return {str(shot.get("id")) for shot in shots if isinstance(shot, dict) and shot.get("id")}


def _planned_budget(notes_path: Path) -> float | None:
    try:
        text = notes_path.read_text(encoding="utf-8")
    except OSError:
        return None
    blocks = re.split(r"(?m)^###\s+Slide\s+", text)[1:]
    if not blocks:
        return None
    total = 0.0
    for block in blocks:
        match = BUDGET_RE.search(block)
        if match is None:
            return None
        value = float(match.group(1))
        if match.group(2).lower().startswith(("分", "min")):
            value *= 60
        total += value
    return round(total, 3)


def visual_problems(
    spec: EpisodeSpec,
    *,
    page_count: int | None,
    shot_ids: set[str] | None,
) -> list[str]:
    """A beat must name what the viewer is looking at, and where it comes from."""
    problems: list[str] = []
    referenced_shots: set[str] = set()
    for beat in spec.beats:
        raw = (beat.visual or "").strip()
        if not raw:
            problems.append(f"{beat.id}: beat.visual is required")
            continue
        parts = [part.strip() for part in raw.split(";") if part.strip()]
        if not parts:
            problems.append(f"{beat.id}: beat.visual is empty")
            continue
        anchor = parts[0]
        if PAGE_PART.match(anchor) is None and SHOT_PART.match(anchor) is None:
            problems.append(
                f"{beat.id}: beat.visual must start with page:N, page:N-M or shot:<id> (got {anchor!r})"
            )
            continue

        for part in parts:
            page_match = PAGE_PART.match(part)
            shot_match = SHOT_PART.match(part)
            if page_match is not None:
                start = int(page_match.group(1))
                end = int(page_match.group(2) or start)
                if start < 1 or end < start:
                    problems.append(f"{beat.id}: page range {start}-{end} is not a forward range")
                elif page_count is not None and end > page_count:
                    problems.append(
                        f"{beat.id}: page range {start}-{end} exceeds the deck ({page_count} pages)"
                    )
            elif shot_match is not None:
                shot_name = shot_match.group(1)
                referenced_shots.add(shot_name)
                if shot_ids is not None and shot_name not in shot_ids:
                    problems.append(
                        f"{beat.id}: shot {shot_name!r} is not in storyboard.yaml"
                    )

        has_shot = any(SHOT_PART.match(part) for part in parts)
        has_static = any(part.lower().startswith("static") for part in parts)
        if has_shot and has_static:
            problems.append(
                f"{beat.id}: beat declares both a shot and 'static' (conflicting visual contract)"
            )
        elif not has_shot:
            has_reason = any("reason:" in part.lower() for part in parts)
            if not (has_static and has_reason):
                problems.append(
                    f"{beat.id}: a beat without a shot needs 'static, reason: ...' "
                    "(say why the page is still)"
                )

    if shot_ids is not None:
        unreferenced = shot_ids - referenced_shots
        if unreferenced:
            problems.append(
                f"storyboard shot(s) not referenced by any beat: {', '.join(sorted(unreferenced))}"
            )
    return problems

PAGE_MARK_RE = re.compile(r"<!--\s*ks:page\s+pdf=(\d+)\s*-->")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(assets/([^)]+)\)")
PAGE_PAIR_RE = re.compile(
    r"printed\s+p\.?\s*(\d+)\s*(?:\(|/)\s*PDF\s+p\.?\s*(\d+)\s*\)?", re.I
)
EVIDENCE_REQUIRED = (
    "figure_id",
    "source_edition",
    "file_path",
    "pristine_path",
    "docling_asset",
    "pixel_policy",
    "printed_page",
    "pdf_page",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _docling_output_root(workspace: Path | None) -> Path | None:
    """Resolve DOCLING_OUTPUT_ROOT from the workspace, then from this checkout."""
    import yaml

    candidates: list[Path] = []
    if workspace is not None:
        candidates.append(Path(workspace).resolve())
    candidates.append(Path(__file__).resolve().parents[4])
    for base in candidates:
        config = base / "config" / "local-paths.yaml"
        if not config.is_file():
            continue
        try:
            data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 - an unreadable config is reported by the caller
            continue
        value = data.get("docling_root") if isinstance(data, dict) else None
        if not value:
            continue
        root = Path(str(value)).expanduser()
        if not root.is_absolute():
            root = base / root
        return (root / "output").resolve()
    return None


def _docling_page_by_asset(bundle: Path) -> dict[str, int]:
    """Map an extracted asset filename to the PDF page Docling recorded for it."""
    markdown = bundle / "document.md"
    if not markdown.is_file():
        return {}
    pages: dict[str, int] = {}
    current: int | None = None
    for line in markdown.read_text(encoding="utf-8").splitlines():
        mark = PAGE_MARK_RE.search(line)
        if mark is not None:
            current = int(mark.group(1))
        image = MD_IMAGE_RE.search(line)
        if image is not None and current is not None:
            pages.setdefault(Path(image.group(1)).name, current)
    return pages


def _pixels_equal(delivered: Path, pristine: Path, box: list[int] | None) -> str | None:
    """None when `delivered` equals `pristine` (optionally cropped); else a reason."""
    try:
        from PIL import Image, ImageChops
    except Exception as exc:  # noqa: BLE001 - PIL is a hard dependency of the capture step
        return f"Pillow is required for pixel checks: {exc}"
    try:
        with Image.open(delivered) as handle:
            left = handle.convert("RGBA")
        with Image.open(pristine) as handle:
            right = handle.convert("RGBA")
        if box is not None:
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= right.width and 0 <= y0 < y1 <= right.height):
                return f"crop_box {box} is outside pristine {right.width}x{right.height}"
            right = right.crop((x0, y0, x1, y1))
        if left.size != right.size:
            return f"size {left.width}x{left.height} != pristine crop {right.width}x{right.height}"
        difference = ImageChops.difference(left, right)
        if any(upper > 0 for _, upper in difference.getextrema()):
            return "pixels differ from pristine"
    except Exception as exc:  # noqa: BLE001 - a broken PNG is a failed pixel check
        return f"cannot compare images: {exc}"
    return None


def evidence_problems(
    lesson_dir: Path,
    workspace: Path | None = None,
    spec: EpisodeSpec | None = None,
) -> tuple[list[str], list[str]]:
    """Lock figures to their Docling export and keep page conventions honest.

    Three hard rules:
    1. ``pristine`` must be byte-identical to the Docling export it names.
    2. A delivered figure is either exact or a declared lossless crop of pristine.
    3. ``pdf_page - printed_page`` is constant per edition, and each ``pdf_page``
       matches the page Docling recorded for that asset.  Free-text pairs in
       slides.md must use one of the known offsets.
    """
    import yaml

    errors: list[str] = []
    warnings: list[str] = []
    lesson_dir = Path(lesson_dir)
    manifest_path = lesson_dir / "authoring" / "evidence.manifest.yaml"
    uses_book = bool(
        spec
        and any(
            str(asset.get("role") or "") in {"book_figure", "paper_figure"}
            for asset in (spec.assets or [])
        )
    )
    if not manifest_path.is_file():
        if uses_book:
            errors.append(
                "assets declare book figures but authoring/evidence.manifest.yaml is missing "
                "(pristine hashes and Docling provenance cannot be checked)"
            )
        return errors, warnings
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - surface the YAML error as a gate
        return [f"cannot read {manifest_path}: {exc}"], warnings
    if not isinstance(data, dict):
        return [f"{manifest_path} must be a mapping"], warnings

    figures = data.get("figures")
    if not isinstance(figures, list) or not figures:
        if uses_book:
            errors.append(f"{manifest_path} has no figures")
        return errors, warnings

    declared: dict[str, int | dict[str, int]] = {}
    raw_offsets = data.get("page_offsets") or {}
    if isinstance(raw_offsets, dict):
        for key, value in raw_offsets.items():
            edition_key = str(key)
            if isinstance(value, dict):
                chapters: dict[str, int] = {}
                for chapter, offset_value in value.items():
                    try:
                        chapters[str(chapter)] = int(offset_value)
                    except (TypeError, ValueError):
                        errors.append(
                            f"page_offsets[{key!r}][{chapter!r}] is not an integer"
                        )
                if chapters:
                    declared[edition_key] = chapters
            else:
                try:
                    declared[edition_key] = int(value)
                except (TypeError, ValueError):
                    errors.append(
                        f"page_offsets[{key!r}] is not an integer or chapter map"
                    )

    docling_output = _docling_output_root(workspace)
    if docling_output is None:
        errors.append(
            "cannot resolve docling_root; pristine hashes cannot be checked against the Docling export"
        )
        docling_output = Path("__missing_docling_root__")

    offsets_by_edition: dict[str, list[tuple[str, int]]] = {}
    page_cache: dict[str, dict[str, int]] = {}

    for index, raw in enumerate(figures, 1):
        if not isinstance(raw, dict):
            errors.append(f"figure #{index} is not a mapping")
            continue
        label = str(raw.get("figure_id") or f"figure #{index}")
        missing = [key for key in EVIDENCE_REQUIRED if raw.get(key) in (None, "")]
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
            continue
        edition = str(raw["source_edition"]).strip()
        delivered = (lesson_dir / str(raw["file_path"])).resolve()
        pristine = (lesson_dir / str(raw["pristine_path"])).resolve()
        docling_asset = (docling_output / str(raw["docling_asset"])).resolve()
        present = True
        for path, label_text in (
            (delivered, "delivered file"),
            (pristine, "pristine file"),
            (docling_asset, "Docling asset"),
        ):
            if not path.is_file():
                errors.append(f"{label}: {label_text} missing: {path}")
                present = False
        if not present:
            continue

        policy = str(raw["pixel_policy"]).strip().lower()
        if policy != "source_export" and _sha256(pristine) != _sha256(docling_asset):
            errors.append(
                f"{label}: pristine is not byte-identical to the Docling export "
                f"({raw['pristine_path']})"
            )
        if policy == "exact":
            if _sha256(delivered) != _sha256(pristine):
                errors.append(
                    f"{label}: delivered image differs from pristine (pixel protection)"
                )
        elif policy == "source_export":
            if _sha256(delivered) != _sha256(pristine):
                errors.append(
                    f"{label}: source-export delivery differs from its pristine export"
                )
            export = raw.get("source_export")
            if not isinstance(export, dict):
                errors.append(
                    f"{label}: source_export policy needs source_export metadata"
                )
            else:
                source_pdf = Path(str(export.get("source_pdf") or "")).expanduser()
                if not source_pdf.is_file():
                    errors.append(f"{label}: source_export PDF missing: {source_pdf}")
                export_page = export.get("pdf_page")
                if export_page != int(raw["pdf_page"]):
                    errors.append(
                        f"{label}: source_export pdf_page {export_page!r} does not "
                        f"match manifest pdf_page {raw['pdf_page']}"
                    )
                minimum_long_edge = int(export.get("minimum_long_edge") or 0)
                if minimum_long_edge < 300:
                    errors.append(
                        f"{label}: source_export minimum_long_edge must be >= 300"
                    )
                try:
                    from PIL import Image

                    with Image.open(delivered) as handle:
                        if max(handle.size) < minimum_long_edge:
                            errors.append(
                                f"{label}: source_export image {handle.size} is below "
                                f"minimum long edge {minimum_long_edge}"
                            )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{label}: cannot inspect source-export image: {exc}")
        elif policy == "crop":
            box = raw.get("crop_box")
            if not (
                isinstance(box, list)
                and len(box) == 4
                and all(isinstance(value, int) for value in box)
            ):
                errors.append(f"{label}: crop policy needs crop_box [x0,y0,x1,y1]")
            else:
                reason = _pixels_equal(delivered, pristine, box)
                if reason is not None:
                    errors.append(
                        f"{label}: crop is not a lossless crop of pristine: {reason}"
                    )
        else:
            errors.append(
                f"{label}: unknown pixel_policy {policy!r} (use exact or crop)"
            )

        try:
            printed = int(raw["printed_page"])
            pdf = int(raw["pdf_page"])
        except (TypeError, ValueError):
            errors.append(f"{label}: printed_page and pdf_page must be integers")
            continue
        offset = pdf - printed
        offsets_by_edition.setdefault(edition, []).append((label, offset))
        expected = declared.get(edition)
        if isinstance(expected, dict):
            chapter = str(raw.get("chapter") or "").strip()
            if not chapter:
                match = re.match(r"§?\s*(\d+)", str(raw.get("section") or ""))
                chapter = match.group(1) if match else ""
            if chapter not in expected:
                errors.append(
                    f"{label}: no page offset declared for chapter {chapter!r} in {edition}"
                )
            elif offset != expected[chapter]:
                errors.append(
                    f"{label}: pdf_page - printed_page = {offset}, expected "
                    f"{expected[chapter]} for {edition} chapter {chapter} "
                    "(mixed page convention)"
                )
        elif isinstance(expected, int) and offset != expected:
            errors.append(
                f"{label}: pdf_page - printed_page = {offset}, expected "
                f"{expected} for {edition} (mixed page convention)"
            )

        # source_edition is a human label ("hucho-en-5e (5th ed., 2016)"), not a
        # directory name. The docling_asset path carries the real bundle id, so
        # resolve from it first; falling back to the label silently skipped the
        # cross-check and reported a warning instead of verifying the page.
        asset_rel = Path(str(raw["docling_asset"]))
        bundle_id = asset_rel.parts[0] if len(asset_rel.parts) > 1 else edition
        if bundle_id not in page_cache:
            page_cache[bundle_id] = _docling_page_by_asset(docling_output / bundle_id)
        asset_page = page_cache[bundle_id].get(asset_rel.name)
        if asset_page is None:
            warnings.append(
                f"{label}: pdf_page {pdf} could not be cross-checked against the Docling page markers"
            )
        elif asset_page != pdf:
            errors.append(
                f"{label}: pdf_page {pdf} does not match the Docling page {asset_page}"
            )

    for edition, rows in offsets_by_edition.items():
        if edition in declared:
            continue
        values = {offset for _, offset in rows}
        if len(values) > 1:
            detail = ", ".join(f"{label}={offset}" for label, offset in rows)
            errors.append(
                f"{edition}: page offset is not constant ({detail}); mixed page convention"
            )
        elif values:
            warnings.append(
                f"{edition}: page offset {next(iter(values))} inferred; declare it under page_offsets"
            )

    allowed: set[int] = set()
    for value in declared.values():
        if isinstance(value, dict):
            allowed.update(value.values())
        else:
            allowed.add(value)
    for rows in offsets_by_edition.values():
        allowed.update(offset for _, offset in rows)
    slides_path = lesson_dir / "slides.md"
    if allowed and slides_path.is_file():
        for lineno, line in enumerate(
            slides_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            for match in PAGE_PAIR_RE.finditer(line):
                printed = int(match.group(1))
                pdf = int(match.group(2))
                if pdf - printed not in allowed:
                    errors.append(
                        f"slides.md:{lineno}: printed p.{printed} (PDF p.{pdf}) has "
                        f"offset {pdf - printed}; known offsets are {sorted(allowed)}"
                    )
    return errors, warnings


def run_preflight(lesson_dir: Path, strict: bool = False, paths=None) -> PreflightReport:
    report = PreflightReport(lesson=lesson_dir.name)
    spec_path = lesson_dir / "authoring" / "episode.spec.yaml"
    rubric_path = lesson_dir / "authoring" / "quality.rubric.yaml"

    try:
        rubric = load_quality_rubric(rubric_path)
    except QualityRubricError as exc:
        report.errors.append(str(exc))
        rubric = None

    try:
        spec = load_episode_spec(spec_path)
        report.spec = spec
    except EpisodeSpecError as exc:
        report.errors.append(str(exc))
        spec = None

    lesson_config = getattr(paths, "lesson", None) if paths is not None else None
    if lesson_config is not None and getattr(lesson_config, "product_tier", None):
        from course_control.production.product import check_product

        product = check_product(lesson_config, lesson_dir)
        report.errors.extend(f"product: {item}" for item in product.errors)
        report.warnings.extend(f"product: {item}" for item in product.warnings)

    if spec is not None:
        if not (spec.min_seconds <= spec.total_seconds <= spec.max_seconds):
            report.errors.append(
                f"beat total {spec.total_seconds}s outside [{spec.min_seconds}, {spec.max_seconds}]"
            )
        voice_status = str((spec.voice or {}).get("status") or "").strip()
        if not voice_status:
            report.errors.append("voice.status is required (owner|cloud|local|tbd|none)")
        elif voice_status == "tbd":
            report.warnings.append("voice.status is tbd; final render requires a decision")
        elif voice_status in {"none", "local"}:
            report.warnings.append(f"voice.status={voice_status}; check delivery requirements")
        rights = spec.rights or {}
        if not rights.get("figures_checked"):
            report.warnings.append("rights.figures_checked is false; publication gate will block")
        for asset in spec.assets or []:
            role = str(asset.get("role") or "").strip()
            if role not in {"render_only", "book_figure", "paper_figure", "data", "schematic"}:
                report.errors.append(f"asset role invalid: {asset}")
            if "drivaer" in str(asset.get("source") or "").lower() and role != "render_only":
                report.errors.append(
                    "DrivAer assets are render-only; they cannot be used as data"
                )
        if rubric is not None and "content" not in rubric.dimensions:
            report.warnings.append("rubric has no content dimension")

        if paths is not None:
            slides_path = paths.content_path(paths.lesson.content.slides)
            notes_path = paths.content_path(paths.lesson.content.notes)
            storyboard_path = paths.storyboard_source
        else:
            slides_path = lesson_dir / "slides.md"
            notes_path = lesson_dir / "lecture_notes.md"
            storyboard_path = lesson_dir / "storyboard.yaml"

        pages = _page_count(slides_path)
        shots = _shot_ids(storyboard_path) if storyboard_path is not None else None
        report.errors.extend(visual_problems(spec, page_count=pages, shot_ids=shots))

        evidence_errors, evidence_warnings = evidence_problems(
            lesson_dir,
            getattr(paths, "workspace", None) if paths is not None else None,
            spec,
        )
        report.errors.extend(evidence_errors)
        report.warnings.extend(evidence_warnings)

        planned = _planned_budget(notes_path) if notes_path.is_file() else None
        if not notes_path.is_file():
            pass  # validate owns V-02 for a missing notes file
        elif planned is None:
            report.errors.append(f"cannot read page budgets from {notes_path}")
        else:
            tolerance = 1.5
            duration = getattr(getattr(paths, "lesson", None), "duration", None) if paths else None
            if duration is not None:
                tolerance = float(getattr(duration, "page_tolerance_seconds", tolerance) or tolerance)
            gap = planned - spec.total_seconds
            if abs(gap) > tolerance:
                report.errors.append(
                    f"page budgets total {planned:.3f}s but the measured beats total "
                    f"{spec.total_seconds:.3f}s (gap {gap:+.3f}s, tolerance {tolerance:g}s)"
                )

    if strict and report.warnings:
        report.errors.extend(report.warnings)
        report.warnings = []
    return report
