"""Write the sound design artifacts: JSON and a readable cue sheet."""
from __future__ import annotations

import json
from pathlib import Path

from course_control.sound.schema import SoundDesign


def _review(design: SoundDesign) -> str:
    lines = [
        f"# Sound design — {design.lesson_id}",
        "",
        f"- content kind: {design.content_kind} → style {design.style}",
        f"- voice cues: {len(design.voice)} · music cues: {len(design.music)} · "
        f"effects: {len(design.sfx)} · ambience: {len(design.ambience)}",
        f"- mix: {design.mix.loudness_lufs:g} LUFS / {design.mix.true_peak_db:g} dBTP / "
        f"duck {design.mix.bgm_duck_db:g} dB",
        f"- errors: {design.errors}, warnings: {design.warnings}",
        "",
        "Listen to the cue sheet before the checks. Silence is a cue here, not an absence.",
        "",
        "## Cue sheet",
        "",
        "| at | track | cue |",
        "| ---: | --- | --- |",
    ]
    for at_s, track, description in design.timeline():
        lines.append(f"| {at_s:g}s | {track} | {description} |")
    if not design.timeline():
        lines.append("| — | — | nothing planned |")

    lines += [
        "",
        "## Voice",
        "",
        "| segment | shot | at | delivery | emphasis | reason |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for cue in design.voice:
        emphasis = ", ".join(cue.emphasis) or "—"
        lines.append(
            f"| {cue.segment_id} | {cue.shot_id} | {cue.at_s:g}s | {cue.delivery} | "
            f"{emphasis} | {cue.reason} |"
        )
    if not design.voice:
        lines.append("| — | — | — | — | — | no voice cues |")

    lines += ["", "## Music", ""]
    if design.music:
        lines += [
            "| window | action | track | gain | mood | reason |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
        for cue in design.music:
            lines.append(
                f"| {cue.start_s:g}–{cue.end_s:g}s | {cue.action} | {cue.track_id or '—'} | "
                f"{cue.gain_db:g} dB | {cue.mood} | {cue.reason} |"
            )
    else:
        lines.append("- none")

    lines += ["", "## Effects", ""]
    if design.sfx:
        lines += [
            "| at | event | source | trigger | visual ref | reason |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for event in design.sfx:
            lines.append(
                f"| {event.at_s:g}s | {event.event} | {event.source} | {event.trigger} | "
                f"{event.visual_ref or '—'} | {event.reason} |"
            )
    else:
        lines.append("- none; an effect needs a picture event to justify it")

    lines += ["", "## Ambience", ""]
    if design.ambience:
        lines += ["| window | source | level | reason |", "| --- | --- | --- | --- |"]
        for cue in design.ambience:
            lines.append(f"| {cue.start_s:g}–{cue.end_s:g}s | {cue.source} | {cue.level} | {cue.reason} |")
    else:
        lines.append("- none")

    for level, title in (("error", "Errors"), ("warning", "Warnings")):
        items = [check for check in design.checks if check.level == level]
        lines += ["", f"## {title} ({len(items)})", ""]
        if not items:
            lines.append("- none")
        for check in items:
            at = f" at {check.at_s:g}s" if check.at_s is not None else ""
            lines.append(f"- `{check.id}`{at}: {check.message}")

    lines += [
        "",
        "## Mix",
        "",
        f"- {design.mix.note}",
        "- narration wins every collision; duck music 6–8 dB under speech",
        "- check the finished mix on headphones, laptop speakers and a phone speaker",
        "- a silent stretch is allowed to be silent",
        "",
    ]
    return "\n".join(lines)


def write_artifacts(design: SoundDesign, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = design.model_dump(mode="json")
    design_path = out_dir / "sound_design.json"
    design_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    review_path = out_dir / "sound_review.md"
    review_path.write_text(_review(design), encoding="utf-8")
    return {"design": design_path, "review": review_path}
