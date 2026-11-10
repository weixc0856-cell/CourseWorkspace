"""Deterministic BGM mixing for a finished lesson video.

The audio plan is data-only; this module consumes it and produces a mixed
master with sidechain ducking and loudness normalisation.  It never guesses a
music file: a missing track or a blocked plan is reported as ``blocked``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .audio_plan import build_audio_plan
from .contracts import Status
from .paths import LessonPaths
from .utils import probe_media, run_command, which_command


class AudioMixError(RuntimeError):
    pass


@dataclass
class MixResult:
    status: Status
    output: Path | None
    report_path: Path
    report: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _load_local_paths(workspace: Path) -> dict:
    path = workspace / "config" / "local-paths.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def bgm_source(workspace: Path, track_id: str) -> Path | None:
    """Resolve a track id against the local BGM library.

    ``bgm_schubert_d664_piano`` maps to
    ``<bgm_root>/schubert_d664_piano.wav``.  The root comes from the local
    (git-ignored) ``config/local-paths.yaml``.
    """
    root = _load_local_paths(workspace).get("bgm_root")
    if not root:
        return None
    name = track_id.removeprefix("bgm_")
    base = Path(str(root))
    for candidate in (base / f"{name}.wav", base / "commons" / f"{name}.wav"):
        if candidate.is_file():
            return candidate
    return None


def _filter_chain(gain_db: float) -> str:
    return (
        f"[1:a]volume={gain_db}dB,highpass=f=70[bgm];"
        "[bgm][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=350[duck];"
        "[0:a][duck]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )


def mix_lesson(
    workspace: Path,
    paths: LessonPaths,
    *,
    source_name: str | None = None,
    output_name: str = "course-video-mixed.mp4",
) -> MixResult:
    workspace = workspace.resolve()
    build_root = paths.build_root
    final_dir = build_root / "final"
    if source_name is None:
        captioned = final_dir / "course-video-captioned.mp4"
        source_name = captioned.name if captioned.is_file() else "course-video.mp4"
    final = final_dir / source_name
    report_path = build_root / "audio" / "mix.json"
    report: dict = {
        "schema_version": 1,
        "lesson": paths.slug,
        "source": str(final),
        "output": None,
        "status": "blocked",
    }

    def finish(status: Status, errors=None, warnings=None, output=None) -> MixResult:
        report["status"] = status.value
        report["errors"] = list(errors or [])
        report["warnings"] = list(warnings or [])
        report["output"] = str(output) if output else None
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return MixResult(
            status=status,
            output=output,
            report_path=report_path,
            report=report,
            errors=list(errors or []),
            warnings=list(warnings or []),
        )

    if not final.is_file():
        return finish(
            Status.SKIPPED, errors=[f"final video not found: {final}"]
        )

    plan = build_audio_plan(paths.lesson)
    report["plan"] = plan.model_dump(mode="json")
    if plan.status != "ready":
        return finish(Status.FAIL, errors=["audio plan is blocked: " + "; ".join(plan.errors)])
    if not plan.cues:
        # BGM-less content (news, formal courses) still needs the same loudness
        # target; skipping the stage silently left those masters quiet.
        return _normalize_without_bgm(
            workspace, paths, final, final_dir / output_name, report, finish
        )

    cue = plan.cues[0]
    if len(plan.cues) > 1:
        return finish(
            Status.FAIL,
            errors=["phase 1 supports exactly one BGM cue per lesson"],
        )
    if cue.start_s > 0.01:
        return finish(
            Status.FAIL,
            errors=["phase 1 requires the BGM cue to start at 0 s"],
        )

    source = bgm_source(workspace, cue.track_id)
    report["cue"] = cue.model_dump(mode="json")
    report["source_track"] = str(source) if source else None
    if source is None:
        return finish(
            Status.FAIL,
            errors=[
                f"BGM track not found for {cue.track_id}; set bgm_root in "
                "config/local-paths.yaml and place <track>.wav under it"
            ],
        )

    info = probe_media(final)
    if not info.has_audio:
        return finish(Status.FAIL, errors=["final video has no audio stream"])
    duration = float(info.duration or 0.0)
    if duration <= 0:
        return finish(Status.FAIL, errors=["final video duration is unknown"])

    output = final_dir / output_name
    command = [
        *which_command("ffmpeg"),
        "-hide_banner",
        "-y",
        "-i",
        str(final),
        "-stream_loop",
        "-1",
        "-i",
        str(source),
        "-filter_complex",
        _filter_chain(cue.gain_db),
        "-map",
        "0:v:0",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-t",
        f"{duration:.3f}",
        "-shortest",
        str(output),
    ]
    result = run_command(
        command,
        workspace,
        timeout=1800,
        log_path=build_root / "logs" / "audio-mix.log",
    )
    report["command"] = command
    if result.exit_code != 0 or not output.is_file():
        return finish(
            Status.FAIL,
            errors=[f"ffmpeg mix failed ({result.exit_code}): {result.stderr[-1200:]}"],
        )

    mixed = probe_media(output)
    report["output_info"] = mixed.as_dict()
    if not mixed.has_audio or (mixed.duration or 0) <= 0:
        return finish(Status.FAIL, errors=["mixed output has no usable audio"])
    if abs((mixed.duration or 0) - duration) > 0.05:
        return finish(
            Status.FAIL,
            errors=[
                f"mixed duration {mixed.duration:.3f}s differs from source {duration:.3f}s"
            ],
        )
    report["attribution"] = cue.attribution
    report["license_status"] = cue.license_status
    return finish(Status.PASS, warnings=list(plan.warnings), output=output)


__all__ = ["AudioMixError", "MixResult", "bgm_source", "mix_lesson"]

def _normalize_without_bgm(
    workspace: Path,
    paths: LessonPaths,
    final: Path,
    output: Path,
    report: dict,
    finish,
) -> MixResult:
    """Single-pass loudness normalisation for lessons with no BGM cue."""
    info = probe_media(final)
    if not info.has_audio:
        return finish(Status.FAIL, errors=["final video has no audio stream"])
    duration = float(info.duration or 0.0)
    if duration <= 0:
        return finish(Status.FAIL, errors=["final video duration is unknown"])

    report["mode"] = "loudness_only"
    report["lufs_target"] = -16.0
    command = [
        *which_command("ffmpeg"),
        "-hide_banner",
        "-y",
        "-i",
        str(final),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-t",
        f"{duration:.3f}",
        str(output),
    ]
    result = run_command(
        command,
        workspace,
        timeout=1800,
        log_path=paths.build_root / "logs" / "audio-mix.log",
    )
    report["command"] = command
    if result.exit_code != 0 or not output.is_file():
        return finish(
            Status.FAIL,
            errors=[f"ffmpeg loudness normalisation failed ({result.exit_code}): {result.stderr[-1200:]}"],
        )

    mixed = probe_media(output)
    report["output_info"] = mixed.as_dict()
    if not mixed.has_audio or (mixed.duration or 0) <= 0:
        return finish(Status.FAIL, errors=["normalised output has no usable audio"])
    if abs((mixed.duration or 0) - duration) > 0.05:
        return finish(
            Status.FAIL,
            errors=[f"normalised duration {mixed.duration:.3f}s differs from source {duration:.3f}s"],
        )
    return finish(
        Status.PASS,
        warnings=["no BGM cue configured; applied loudness normalisation only"],
        output=output,
    )
