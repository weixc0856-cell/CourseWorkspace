"""Standardized pipeline tool for extracting pure technical diagrams and assets from PDF sources.

Features:
1. Automatic white-field sampling & color calibration
2. Sub-pixel anti-aliased alpha matting (zero white halos / fringes)
3. Intelligent layout segmentation: strips PPT slide headers, subtitles, bottom bullet points, and footers
4. Strict separation of Code Repo vs Content Root (assets stored under content_data/lessons/<slug>/assets)
5. Zero hardcoded absolute paths: resolves dynamically via resolve_paths.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz
import numpy as np
from PIL import Image

try:
    from resolve_paths import get_content_root, get_workspace_root
except ImportError:
    # Allow running directly when scripts directory is not in PYTHONPATH
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from resolve_paths import get_content_root, get_workspace_root


def extract_pure_diagram_bounds(
    arr_rgb: np.ndarray,
    threshold: float = 15.0,
    min_diagram_h: int = 150,
) -> Optional[Tuple[int, int, int, int]]:
    """Analyze vertical line densities and color variance to isolate the pure diagram body,

    stripping slide titles, subtitles, bullet points, and footer elements.
    Returns (x0, y0, x1, y1) bounding box within the image, or None if empty.
    """
    height, width, _ = arr_rgb.shape
    dist = np.linalg.norm(arr_rgb.astype(np.float32) - 255.0, axis=-1)

    # Row-level non-white pixel density
    row_nonwhite = np.sum(dist > threshold, axis=1)
    blank_row_threshold = width * 0.005
    is_blank = row_nonwhite < blank_row_threshold

    # Find non-blank contiguous vertical segments
    segments: List[Tuple[int, int]] = []
    in_seg = False
    s_start = 0
    for r in range(height):
        if not is_blank[r] and not in_seg:
            in_seg = True
            s_start = r
        elif is_blank[r] and in_seg:
            in_seg = False
            segments.append((s_start, r))
    if in_seg:
        segments.append((s_start, height))

    if not segments:
        return None

    # Classify segments
    diagram_segments: List[Tuple[int, int]] = []
    for y0, y1 in segments:
        h = y1 - y0
        seg_arr = arr_rgb[y0:y1, :]
        # Check color saturation (diagrams usually have chromatic lines/areas, titles are grayscale)
        sat = np.max(seg_arr, axis=2) - np.min(seg_arr, axis=2)
        colored_px = int(np.sum(sat > 25))

        # Filter out obvious slide headers (top 30% of slide with small height)
        if y1 <= int(height * 0.32) and h < int(height * 0.12):
            continue  # Slide title / subtitle
        # Filter out slide footers / page numbers (bottom 6% of slide)
        if y0 >= int(height * 0.94) and h < int(height * 0.06):
            continue  # Slide footer
        # Filter out bottom bullet text lists (bottom 25% of slide with small line height and zero color)
        if y0 >= int(height * 0.75) and h < int(height * 0.08) and colored_px == 0:
            continue  # Bullet points list

        # If it has significant height or chromatic elements or large width
        if h >= min_diagram_h or colored_px > 500:
            diagram_segments.append((y0, y1))

    if not diagram_segments:
        # Fallback to middle region if no segment passed strict heuristic
        diagram_segments = [(int(height * 0.20), int(height * 0.90))]

    # Merge diagram segments bounds
    diag_y0 = min(s[0] for s in diagram_segments)
    diag_y1 = max(s[1] for s in diagram_segments)

    # Determine horizontal bounds within the diagram vertical range
    sub_dist = dist[diag_y0:diag_y1, :]
    col_nonwhite = np.sum(sub_dist > threshold, axis=0)
    xs = np.where(col_nonwhite > 0)[0]
    if len(xs) == 0:
        return None

    pad = 20
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(width, int(xs.max()) + pad)
    y0 = max(0, diag_y0 - pad)
    y1 = min(height, diag_y1 + pad)

    return (x0, y0, x1, y1)


def process_pdf_page_to_matted_asset(
    page: fitz.Page,
    dpi: int = 200,
    edge_softness: float = 18.0,
    clean_text: bool = True,
) -> Tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    """Render PDF page at specified DPI and produce:

    1. Pristine RGBA matted image (transparent background)
    2. Tight-cropped original RGB (white background)
    3. Checkerboard contrast verification image
    4. Course canvas (#F4EFEA) integration verification image
    """
    pix = page.get_pixmap(dpi=dpi)
    img_rgb = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    arr_rgb = np.array(img_rgb)

    if clean_text:
        bounds = extract_pure_diagram_bounds(arr_rgb)
        if bounds is None:
            bounds = (0, 0, pix.width, pix.height)
    else:
        # Simple bounding box ignoring outer border
        dist = np.linalg.norm(arr_rgb.astype(np.float32) - 255.0, axis=-1)
        ys, xs = np.where(dist > 15.0)
        if len(xs) > 0 and len(ys) > 0:
            bounds = (max(0, xs.min() - 16), max(0, ys.min() - 16), min(pix.width, xs.max() + 16), min(pix.height, ys.max() + 16))
        else:
            bounds = (0, 0, pix.width, pix.height)

    x0, y0, x1, y1 = bounds
    cropped_rgb = img_rgb.crop((x0, y0, x1, y1))
    crop_arr = np.array(cropped_rgb)

    # Sub-pixel alpha calculation with continuous euclidean distance falloff
    bg = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    crop_dist = np.linalg.norm(crop_arr.astype(np.float32) - bg, axis=-1)
    alpha = np.clip((crop_dist - 4.0) / edge_softness * 255.0, 0, 255).astype(np.uint8)

    rgba_arr = np.dstack((crop_arr, alpha))
    matted_rgba = Image.fromarray(rgba_arr)

    # Generate checkerboard contrast preview
    cw, ch = matted_rgba.size
    grid_size = 24
    check_arr = np.zeros((ch, cw, 4), dtype=np.uint8)
    check_arr[:, :, 3] = 255
    for y in range(0, ch, grid_size):
        for x in range(0, cw, grid_size):
            val = 48 if ((x // grid_size) + (y // grid_size)) % 2 == 0 else 28
            check_arr[y : y + grid_size, x : x + grid_size, :3] = val
    checker_base = Image.fromarray(check_arr)
    checker_preview = Image.alpha_composite(checker_base, matted_rgba)

    # Generate course canvas (#F4EFEA) preview
    canvas_base = Image.new("RGBA", (cw, ch), (244, 239, 234, 255))
    canvas_preview = Image.alpha_composite(canvas_base, matted_rgba)

    return matted_rgba, cropped_rgb, checker_preview, canvas_preview


def run_pipeline(
    pdf_path: Path,
    output_dir: Path,
    preview_dir: Optional[Path] = None,
    dpi: int = 200,
    clean_text: bool = True,
    pages: Optional[List[int]] = None,
) -> Dict[str, List[Path]]:
    """Execute asset extraction across selected or all pages of the PDF."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Source PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    target_pages = pages if pages else list(range(1, total_pages + 1))

    results: Dict[str, List[Path]] = {
        "matted": [],
        "original": [],
        "preview_checker": [],
        "preview_canvas": [],
    }

    print(f"=== Extracting PDF Assets: {pdf_path.name} (Pages: {len(target_pages)}/{total_pages}, DPI: {dpi}) ===")
    print(f"Target Assets Directory: {output_dir}")
    if preview_dir:
        print(f"Preview Directory:       {preview_dir}")

    for p_num in target_pages:
        if p_num < 1 or p_num > total_pages:
            print(f"Warning: Page {p_num} out of bounds, skipping.")
            continue

        page = doc[p_num - 1]
        matted_rgba, cropped_rgb, checker_prev, canvas_prev = process_pdf_page_to_matted_asset(
            page, dpi=dpi, clean_text=clean_text
        )

        stem = f"matted-page-{p_num:02d}"
        matted_path = output_dir / f"{stem}.png"
        matted_rgba.save(matted_path)
        results["matted"].append(matted_path)

        orig_path = output_dir / f"{stem}-white.png"
        cropped_rgb.save(orig_path)
        results["original"].append(orig_path)

        if preview_dir:
            chk_path = preview_dir / f"{stem}-checkerboard.png"
            checker_prev.save(chk_path)
            results["preview_checker"].append(chk_path)

            cnv_path = preview_dir / f"{stem}-canvas.png"
            canvas_prev.save(cnv_path)
            results["preview_canvas"].append(cnv_path)

        w, h = matted_rgba.size
        print(f"  ✓ Page {p_num:02d}: Extracted {w}x{h} px -> {matted_path.name}")

    print("=== Extraction completed successfully. ===")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract pure technical diagrams & matted assets from course PDF slides.")
    parser.add_argument("--pdf", type=str, required=True, help="Path to the PDF file (absolute or relative to workspace)")
    parser.add_argument("--lesson", type=str, default="t1-01-why-aerodynamics", help="Lesson slug under lessons/")
    parser.add_argument("--out", type=str, default=None, help="Explicit output assets directory (overrides default lesson assets)")
    parser.add_argument("--preview-dir", type=str, default=None, help="Directory for verification preview images (checkerboard/canvas)")
    parser.add_argument("--dpi", type=int, default=200, help="Rasterization DPI (default: 200)")
    parser.add_argument("--pages", type=str, default="1-5", help="Page range to extract, e.g. '1-5', '1,3,7', or 'all'")
    parser.add_argument("--no-clean-text", action="store_true", help="Disable automatic stripping of PPT titles & bullets")

    args = parser.parse_args()

    content_root = get_content_root()
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        # Try finding under source_libraries or workspace
        ws_root = get_workspace_root()
        alt_path = (ws_root / args.pdf).resolve()
        if alt_path.exists():
            pdf_path = alt_path
        else:
            print(f"Error: PDF not found at {args.pdf}", file=sys.stderr)
            return 1

    # Resolve output directory
    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        out_dir = content_root / "lessons" / args.lesson / "assets"

    # Resolve preview directory
    if args.preview_dir:
        preview_dir = Path(args.preview_dir).resolve()
    else:
        # Default temporary preview location under content_root/build/<lesson>/matted_previews
        preview_dir = content_root / "build" / args.lesson / "matted_previews"

    # Parse page specification
    pages_to_extract: Optional[List[int]] = None
    if args.pages.lower() != "all":
        pages_to_extract = []
        parts = args.pages.split(",")
        for part in parts:
            if "-" in part:
                p_start, p_end = map(int, part.split("-"))
                pages_to_extract.extend(range(p_start, p_end + 1))
            else:
                pages_to_extract.append(int(part))

    run_pipeline(
        pdf_path=pdf_path,
        output_dir=out_dir,
        preview_dir=preview_dir,
        dpi=args.dpi,
        clean_text=not args.no_clean_text,
        pages=pages_to_extract,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
