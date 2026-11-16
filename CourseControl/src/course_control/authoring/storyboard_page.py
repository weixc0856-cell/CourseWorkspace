"""Static storyboard pages: the sign-off artifact between storyboard and motion.

The gate in CLAUDE.md §12 says a lesson first ships a paginated, motion-free
storyboard page; only after the owner signs it may narration, effects or the
render run.  This module builds that page from the *effective* storyboard
(``storyboard.yaml`` or the production source) and the slide captures that
already exist in ``build/<slug>/slides/``.

Images are embedded as data URIs so the signed copy is self-contained: replacing
a capture later cannot change what the owner reviewed.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

STYLE_RE = re.compile(r"<style\b.*?</style>", re.DOTALL | re.IGNORECASE)
HEADING_RE = re.compile(r"<h([12])\b[^>]*>(.*?)</h\1>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Page:
    number: int
    title: str
    image: Path | None
    shots: list[dict]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(fragment: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", fragment)).split())


def split_slides(text: str) -> list[str]:
    """Return one title per slide page. Pages are separated by a ``---`` line."""
    body = STYLE_RE.sub("", text)
    if not body.strip():
        return []
    titles: list[str] = []
    for index, part in enumerate(re.split(r"(?m)^---[ \t]*$", body), start=1):
        match = HEADING_RE.search(part)
        title = _text(match.group(2)) if match else ""
        titles.append(title or f"Page {index}")
    return titles


def _capture(slides_dir: Path, number: int) -> Path | None:
    """Return a non-empty, decodable capture at a usable size."""
    for pattern in (f"slide-{number:03d}.png", f"page-{number:03d}.png"):
        candidate = slides_dir / pattern
        if not candidate.is_file() or candidate.stat().st_size == 0:
            continue
        try:
            with Image.open(candidate) as image:
                image.verify()
            with Image.open(candidate) as image:
                if image.width < 16 or image.height < 9:
                    continue
        except Exception:  # noqa: BLE001 - a broken image is a missing capture
            continue
        return candidate
    return None


def _data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _effective_storyboard(lesson_dir: Path, lesson: dict, override: Path | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    relative = (lesson.get("content") or {}).get("storyboard") or "storyboard.yaml"
    return (lesson_dir / relative).resolve()


def collect(
    lesson_dir: Path,
    build_root: Path,
    storyboard_path: Path | None = None,
    storyboard_data: Any | None = None,
) -> tuple[str, list[Page], str, str, list[dict]]:
    lesson_path = lesson_dir / "lesson.yaml"
    lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8")) or {}
    storyboard_path = _effective_storyboard(lesson_dir, lesson, storyboard_path)
    if not storyboard_path.is_file():
        raise FileNotFoundError(f"storyboard not found: {storyboard_path}")
    if storyboard_data is not None:
        storyboard = (
            storyboard_data.model_dump(mode="json")
            if hasattr(storyboard_data, "model_dump")
            else storyboard_data
        )
    else:
        storyboard = yaml.safe_load(storyboard_path.read_text(encoding="utf-8")) or {}

    slides_rel = (lesson.get("content") or {}).get("slides") or "slides.md"
    slides_path = lesson_dir / slides_rel
    titles = split_slides(slides_path.read_text(encoding="utf-8")) if slides_path.is_file() else []
    slides_md_sha = _sha(slides_path) if slides_path.is_file() else ""
    slides_dir = build_root / "slides"

    raw_by_id: dict[str, dict] = {}
    if storyboard_path.name == "production.yaml":
        try:
            raw_plan = yaml.safe_load(storyboard_path.read_text(encoding="utf-8")) or {}
            for sequence in raw_plan.get("sequences") or []:
                for raw_shot in sequence.get("shots") or []:
                    if isinstance(raw_shot, dict) and raw_shot.get("id"):
                        raw_by_id[str(raw_shot["id"])] = raw_shot
        except (OSError, yaml.YAMLError):
            raw_by_id = {}

    by_slide: dict[int, list[dict]] = {}
    for shot in storyboard.get("shots") or []:
        if raw_by_id:
            merged = dict(raw_by_id.get(str(shot.get("id")), {}))
            merged.update(shot)
            shot = merged
        try:
            slide = int(shot.get("slide"))
        except (TypeError, ValueError):
            continue
        by_slide.setdefault(slide, []).append(dict(shot))

    total = max([len(titles), *by_slide.keys()], default=0)
    if total < 1:
        raise ValueError("storyboard has no pages; add slides or shots before review")
    pages: list[Page] = []
    slide_hashes: list[dict] = []
    for number in range(1, total + 1):
        shots = by_slide.get(number, [])
        fallback = ""
        if shots:
            first = shots[0]
            fallback = str(first.get("purpose") or first.get("visual_type") or first.get("id") or "")
        from_slides = titles[number - 1] if number <= len(titles) else ""
        title = from_slides if from_slides and not from_slides.startswith("Page ") else (fallback or f"Page {number}")
        image = _capture(slides_dir, number)
        if image is not None:
            slide_hashes.append({"page": number, "path": image.relative_to(build_root).as_posix(), "sha256": _sha(image)})
        pages.append(Page(number=number, title=title, image=image, shots=shots))
    return (
        str(lesson.get("title_en") or lesson.get("lesson_id") or lesson_dir.name),
        pages,
        _sha(storyboard_path),
        slides_md_sha,
        slide_hashes,
    )


def _shot_html(shot: dict) -> str:
    rows = []
    for label, value in shot.items():
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        rows.append(f"<dt>{html.escape(str(label))}</dt><dd>{html.escape(str(value))}</dd>")
    if not rows:
        rows.append("<dt>shot</dt><dd class=\"missing\">no fields</dd>")
    return f"<article class=\"shot\"><dl>{''.join(rows)}</dl></article>"


def render(lesson_title: str, pages: list[Page], *, storyboard_sha: str, lesson: str) -> str:
    shots = sum(len(page.shots) for page in pages)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    nav = "".join(f"<a href=\"#p{page.number}\">{page.number:02d}</a>" for page in pages)
    sections = []
    for page in pages:
        if page.image is not None:
            media = (
                f"<img src=\"{_data_uri(page.image)}\" "
                f"alt=\"slide {page.number}\" loading=\"eager\">"
            )
        else:
            media = "<div class=\"nocap\">no slide capture for this page</div>"
        shot_html = "".join(_shot_html(shot) for shot in page.shots) or (
            "<p class=\"noshot\">no shot on this page</p>"
        )
        sections.append(
            f"""<section class="page" id="p{page.number}">
  <header class="band"><span>Page {page.number:02d} / {len(pages):02d}</span><h2>{html.escape(page.title)}</h2><span>{len(page.shots)} shot(s)</span></header>
  <div class="frame">{media}</div>
  <aside class="shots">{shot_html}
    <div class="checks">
      <p>Cover the labels and answer:</p>
      <ol>
        <li>Does the picture show what this page claims?</li>
        <li>Are the subject, field quantities and labels in the place physics or the evidence puts them?</li>
        <li>Do the numbers in the caption match the geometry?</li>
      </ol>
    </div>
  </aside>
</section>"""
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storyboard review · {html.escape(lesson)}</title>
<style>
  :root {{ --paper:#EDE7DA; --ink:#252A31; --muted:#6B6F76; --line:#CFCABE; --hot:#E8733B; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#F7F5EF; color:var(--ink); font:15px/1.5 "Segoe UI", system-ui, sans-serif; }}
  .cover {{ max-width:1180px; margin:0 auto; padding:48px 32px 24px; }}
  .cover h1 {{ font-size:28px; margin:0 0 6px; }}
  .cover p {{ margin:4px 0; color:var(--muted); }}
  .cover .gate {{ margin-top:16px; padding:10px 14px; border-left:4px solid var(--hot); background:#fff; color:var(--ink); }}
  .cover nav {{ margin-top:16px; display:flex; flex-wrap:wrap; gap:6px; }}
  .cover nav a {{ display:inline-block; padding:2px 7px; border:1px solid var(--line); color:var(--ink); text-decoration:none; font-variant-numeric:tabular-nums; }}
  .page {{ max-width:1180px; margin:24px auto 40px; padding:24px 32px; background:var(--paper); border:1px solid var(--line); }}
  .band {{ display:flex; align-items:baseline; gap:16px; border-bottom:1px solid var(--line); padding-bottom:10px; }}
  .band h2 {{ flex:1; margin:0; font-size:20px; }}
  .band span {{ color:var(--muted); font-size:12px; letter-spacing:.08em; text-transform:uppercase; }}
  .frame {{ margin-top:18px; background:#fff; border:1px solid var(--line); aspect-ratio:16/9; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
  .frame img {{ width:100%; height:100%; object-fit:contain; }}
  .nocap {{ color:var(--muted); font-size:13px; }}
  .shots {{ display:grid; gap:12px; margin-top:16px; }}
  .shot {{ background:#fff; border:1px solid var(--line); padding:12px 14px; }}
  .shot dl {{ display:grid; grid-template-columns:150px 1fr; gap:4px 14px; margin:0; }}
  .shot dt {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
  .shot dd {{ margin:0; word-break:break-word; }}
  .missing {{ color:var(--hot); }}
  .noshot {{ color:var(--muted); font-size:13px; margin:0; }}
  .checks {{ margin-top:12px; padding:12px 14px; border:1px dashed var(--line); }}
  .checks p {{ margin:0 0 6px; font-weight:600; }}
  .checks ol {{ margin:0; padding-left:20px; color:var(--muted); }}
  footer {{ max-width:1180px; margin:0 auto 48px; padding:0 32px; color:var(--muted); font-size:12px; }}
  @media print {{
    body {{ background:#fff; }}
    .cover nav {{ display:none; }}
    .page {{ border:0; margin:0; page-break-after:always; max-width:none; }}
  }}
</style>
</head>
<body>
<header class="cover">
  <h1>{html.escape(lesson_title)}</h1>
  <p>{html.escape(lesson)} · {len(pages)} pages · {shots} shots · generated {html.escape(generated)}</p>
  <p>storyboard sha256: {html.escape(storyboard_sha[:16])}…</p>
  <p class="gate">Sign-off gate: no motion, narration or render before this page is approved page by page.</p>
  <nav>{nav}</nav>
</header>
{''.join(sections)}
<footer>Static storyboard page. Images are embedded; no animation, no audio. Built from the effective storyboard and build/&lt;slug&gt;/slides/slide-###.png.</footer>
</body>
</html>
"""


def build(
    lesson: str,
    lesson_dir: Path,
    build_root: Path,
    storyboard_path: Path | None = None,
    storyboard_data: Any | None = None,
) -> dict:
    title, pages, storyboard_sha, slides_md_sha, slide_hashes = collect(
        lesson_dir, build_root, storyboard_path, storyboard_data
    )
    out = build_root / "storyboard"
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / "index.html"
    html_path.write_text(
        render(title, pages, storyboard_sha=storyboard_sha, lesson=lesson), encoding="utf-8"
    )
    missing = [page.number for page in pages if page.image is None]
    manifest = {
        "schema_version": 1,
        "lesson": lesson,
        "title": title,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "storyboard_path": str(Path(storyboard_path).resolve()) if storyboard_path else "lesson.content.storyboard",
        "storyboard_sha256": storyboard_sha,
        "slides_md_sha256": slides_md_sha,
        "slides": slide_hashes,
        "pages": len(pages),
        "shots": sum(len(page.shots) for page in pages),
        "pages_detail": [
            {
                "page": page.number,
                "title": page.title,
                "shots": [str(shot.get("id") or "") for shot in page.shots],
            }
            for page in pages
        ],
        "missing_captures": missing,
        "ready": not missing,
        "html": str(html_path),
        "html_sha256": _sha(html_path),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
