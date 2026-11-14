"""Preview mix for the sound design layer.

The release mix is still the BGM-only path in ``voice/audio_mix.py``.  A preview
needs to answer a different question: does the film work with music, effects and
ambience in the right places?  This module reads ``sound/sound_design.json`` and
mixes whatever assets actually exist.  Missing assets are warnings, not fails.
"""

from __future__ import annotations

import json
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.platform.utils import run_command, which_command

DESIGN_FILE = Path("sound") / "sound_design.json"


def load_design(paths: LessonPaths) -> dict | None:
    path = paths.build_root / DESIGN_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _resolve(paths: LessonPaths, value: str) -> Path | None:
    raw = Path(value)
    if raw.is_absolute():
        return raw if raw.is_file() else None
    for base in (paths.lesson_dir, paths.content_base or paths.workspace, paths.workspace):
        candidate = (base / raw).resolve()
        if candidate.is_file():
            return candidate
    return None


def _music_source(paths: LessonPaths, track_id: str | None) -> Path | None:
    if not track_id:
        return None
    try:
        from course_control.voice.audio_mix import bgm_source

        return bgm_source(paths.workspace, track_id)
    except Exception:  # noqa: BLE001
        return None


def mix_preview(
    paths: LessonPaths,
    video: Path,
    output: Path,
) -> tuple[Path | None, list[str]]:
    """Mix the designed cues into ``video`` for preview only."""
    design = load_design(paths)
    warnings: list[str] = []
    if design is None:
        return None, ["no sound_design.json; preview keeps narration only"]

    inputs: list[Path] = []
    filters: list[str] = []
    labels: list[str] = []

    def add_input(source: Path, start_s: float, duration_s: float, gain_db: float, label: str) -> None:
        index = len(inputs) + 1
        inputs.append(source)
        delay = max(0, int(round(start_s * 1000)))
        filters.append(
            f"[{index}:a]atrim=0:{max(0.1, duration_s):.3f},asetpts=PTS-STARTPTS,"
            f"volume={gain_db}dB,adelay={delay}|{delay}[{label}]"
        )
        labels.append(label)

    for cue in design.get("music") or []:
        if not isinstance(cue, dict) or cue.get("action") == "silence":
            continue
        source = _music_source(paths, cue.get("track_id"))
        if source is None:
            continue
        start = float(cue.get("start_s") or 0.0)
        end = float(cue.get("end_s") or start + 1.0)
        add_input(source, start, max(0.1, end - start), float(cue.get("gain_db", -25.0)), f"m{len(labels)}")

    for event in design.get("sfx") or []:
        if not isinstance(event, dict) or not event.get("source"):
            continue
        source = _resolve(paths, str(event["source"]))
        if source is None:
            warnings.append(f"sfx asset missing: {event['source']}")
            continue
        add_input(source, float(event.get("at_s") or 0.0), 3.0, -18.0, f"s{len(labels)}")

    for cue in design.get("ambience") or []:
        if not isinstance(cue, dict) or not cue.get("source"):
            continue
        source = _resolve(paths, str(cue["source"]))
        if source is None:
            warnings.append(f"ambience asset missing: {cue['source']}")
            continue
        start = float(cue.get("start_s") or 0.0)
        end = float(cue.get("end_s") or start + 1.0)
        add_input(source, start, max(0.1, end - start), -30.0, f"a{len(labels)}")

    if not labels:
        return None, warnings + ["no resolvable sound-design assets; preview keeps narration only"]

    filters.append(
        "[0:a]" + "".join(f"[{label}]" for label in labels)
        + f"amix=inputs={len(labels) + 1}:duration=first:dropout_transition=0:normalize=0[a]"
    )
    command = [
        *which_command("ffmpeg"),
        "-v",
        "error",
        "-y",
        "-i",
        str(video),
    ]
    for source in inputs:
        command.extend(["-i", str(source)])
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )
    result = run_command(
        command,
        paths.workspace,
        timeout=1800,
        log_path=paths.build_root / "preview" / "logs" / "sound-mix.log",
    )
    if result.exit_code != 0:
        return None, warnings + [f"sound mix failed: {result.stderr[-800:]}"]
    return output, warnings


__all__ = ["load_design", "mix_preview"]
