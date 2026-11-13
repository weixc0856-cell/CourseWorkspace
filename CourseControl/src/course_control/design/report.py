"""Write the visual design artifacts: JSON, boards, contact sheet, review."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable

from course_control.design.board import board_svg
from course_control.design.schema import DesignCheck, ShotDesign, VisualDesign


def _review(document: VisualDesign) -> str:
    by_shot: dict[str, list[DesignCheck]] = {}
    for check in document.checks:
        if check.shot_id:
            by_shot.setdefault(check.shot_id, []).append(check)

    lines = [
        f"# Visual design review — {document.lesson_id}",
        "",
        f"- shots: {len(document.shots)}",
        f"- default theme: {document.theme_default} (page colour {document.lesson_style_background})",
        f"- authored: {sum(1 for shot in document.shots if shot.authorship == 'authored')} / "
        f"derived: {sum(1 for shot in document.shots if shot.authorship == 'derived')}",
        f"- errors: {document.errors}, warnings: {document.warnings}",
        "",
        "Look at the boards before reading the checks. A design that passes every rule can",
        "still be dull; a design that fails one can still be right.",
        "",
        "## Shots",
        "",
        "| shot | seconds | family | theme | focal object | depth | authorship | findings |",
        "| --- | ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for shot in document.shots:
        findings = by_shot.get(shot.shot_id, [])
        lines.append(
            f"| {shot.shot_id} | {shot.duration_s:g} | {shot.art_direction.family} | "
            f"{shot.art_direction.theme} | {shot.composition.focal_object} | "
            f"{len(shot.composition.depth_layers)} | {shot.authorship} | {len(findings)} |"
        )

    for level, title in (("error", "Errors"), ("warning", "Warnings")):
        items = [check for check in document.checks if check.level == level]
        lines += ["", f"## {title} ({len(items)})", ""]
        if not items:
            lines.append("- none")
        for check in items:
            target = f" `{check.shot_id}`" if check.shot_id else ""
            lines.append(f"- `{check.id}`{target}: {check.message}")

    infos = [check for check in document.checks if check.level == "info"]
    if infos:
        lines += ["", "## Notes", ""]
        lines.extend(f"- `{check.id}`: {check.message}" for check in infos)

    lines += [
        "",
        "## Boards",
        "",
        "- `boards/<shot>.svg` shows start / turn / end, the depth layers and the focal object.",
        "- `index.html` shows every board in shot order.",
        "",
        "## Next step",
        "",
        "- Replace a derived design you disagree with in `authoring/visual-design.yaml`.",
        "- A shot's design is not accepted because these checks pass; it is accepted after the",
        "  rendered shot is watched without narration.",
        "",
    ]
    return "\n".join(lines)


def _index(document: VisualDesign) -> str:
    cards: list[str] = []
    for shot in document.shots:
        checks = [item for item in document.checks if item.shot_id == shot.shot_id]
        errors = sum(1 for item in checks if item.level == "error")
        warnings = sum(1 for item in checks if item.level == "warning")
        tone = "error" if errors else ("warn" if warnings else "ok")
        cards.append(
            f'<a class="card {tone}" href="boards/{shot.shot_id}.svg">'
            f'<img src="boards/{shot.shot_id}.svg" alt="{html.escape(shot.title)} board">'
            f'<div class="meta"><strong>{shot.shot_id}</strong> · {shot.duration_s:g}s · '
            f'{shot.art_direction.family} · {shot.authorship}'
            f'<span>{html.escape(shot.title)}</span></div></a>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visual design — {html.escape(document.lesson_id)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; padding: 32px; background: #FBFAF7; color: #252A31;
         font: 14px/1.5 Inter, "Segoe UI", Helvetica, Arial, sans-serif; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  p.sub {{ margin: 0 0 24px; color: #6B7280; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; }}
  .card {{ display: block; text-decoration: none; color: inherit; border: 1px solid #E3E0D7;
           border-radius: 8px; overflow: hidden; background: #fff; }}
  .card img {{ display: block; width: 100%; height: auto; }}
  .card.error {{ border-color: #C75B55; }}
  .card.warn {{ border-color: #E8A33D; }}
  .meta {{ padding: 10px 12px; font-size: 12px; color: #6B7280; }}
  .meta strong {{ color: #252A31; }}
  .meta span {{ display: block; color: #2E3338; font-size: 13px; margin-top: 2px; }}
</style>
</head>
<body>
<h1>Visual design — {html.escape(document.lesson_id)}</h1>
<p class="sub">{len(document.shots)} shots · theme {document.theme_default} ·
{sum(1 for s in document.shots if s.authorship == 'authored')} authored ·
{sum(1 for s in document.shots if s.authorship == 'derived')} derived ·
{document.errors} errors · {document.warnings} warnings</p>
<div class="grid">
{chr(10).join(cards)}
</div>
</body>
</html>
"""


def write_artifacts(
    document: VisualDesign,
    out_dir: Path,
    theme_loader: Callable[[str], dict],
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    boards = out_dir / "boards"
    boards.mkdir(exist_ok=True)

    payload = document.model_dump(mode="json")
    design_path = out_dir / "visual_design.json"
    design_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for shot in document.shots:
        theme = theme_loader(shot.art_direction.theme)
        (boards / f"{shot.shot_id}.svg").write_text(board_svg(shot, theme), encoding="utf-8")

    index_path = out_dir / "index.html"
    index_path.write_text(_index(document), encoding="utf-8")

    review_path = out_dir / "design_review.md"
    review_path.write_text(_review(document), encoding="utf-8")

    return {"design": design_path, "boards": boards, "index": index_path, "review": review_path}


def shot_summary(shot: ShotDesign) -> str:
    return (
        f"{shot.shot_id} {shot.art_direction.family}/{shot.art_direction.theme} "
        f"focus={shot.composition.focal_object} depth={len(shot.composition.depth_layers)}"
    )
