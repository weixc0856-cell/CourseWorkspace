"""Preview-only audio: narration is already in the Remotion render; this adds
the declared music bed so a P2 preview can be judged as a whole.

The mix is deliberately simple and is never used for delivery.  It keeps the
music low, loops it to picture length and leaves the narration in front.
"""

from __future__ import annotations

from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.platform.utils import run_command, which_command


def resolve_music(paths: LessonPaths) -> Path | None:
    cues = paths.lesson.audio.bgm
    if not cues:
        return None
    try:
        from course_control.voice.audio_mix import bgm_source

        return bgm_source(paths.workspace, cues[0].track_id)
    except Exception:  # noqa: BLE001 - a missing track is a warning, not a failure
        return None


def mix_music(
    workspace: Path,
    video: Path,
    music: Path,
    output: Path,
    *,
    gain_db: float = -22.0,
) -> tuple[Path | None, str | None]:
    if not music.is_file():
        return None, f"music not found: {music}"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-filter_complex",
            (
                f"[1:a]volume={gain_db}dB[music];"
                "[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[a]"
            ),
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
        ],
        workspace,
        timeout=1800,
        log_path=output.parent.parent / "logs" / "preview-mix.log",
    )
    if result.exit_code != 0:
        return None, f"preview mix failed: {result.stderr[-800:]}"
    return output, None


__all__ = ["mix_music", "resolve_music"]
