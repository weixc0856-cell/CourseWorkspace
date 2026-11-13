"""Sound checks: the ways a soundtrack stops serving the explanation.

Advisory by design.  The mix is judged by listening; these rules only catch the
mistakes that are visible before anyone listens — an effect on every node, a
theme that never rests, music under the one paragraph that needed silence.
"""
from __future__ import annotations

from course_control.sound.schema import SoundCheck, SoundDesign


def _window_density(events: list[float], window_s: float = 20.0) -> int:
    best = 0
    for start in events:
        count = sum(1 for at in events if start <= at < start + window_s)
        best = max(best, count)
    return best


def _runs(cues) -> list[tuple[float, float]]:
    return sorted((cue.start_s, cue.end_s) for cue in cues)


def _longest_run(cues) -> float:
    longest = 0.0
    for start, end in _runs(cues):
        current = end - start
        longest = max(longest, current)
    return longest


def check_sound(design: SoundDesign, *, has_visual_design: bool, has_narration: bool) -> list[SoundCheck]:
    checks: list[SoundCheck] = []

    if has_narration and not design.voice:
        checks.append(
            SoundCheck(
                id="sound.voice_missing",
                level="error",
                rule="every narrated lesson has voice cues",
                message="the director plan carries narration but the sound design has none",
            )
        )

    for cue in design.music:
        if cue.track_id and cue.license_status == "unknown":
            checks.append(
                SoundCheck(
                    id="sound.licence_unknown",
                    level="error",
                    rule="a track without a known licence never reaches a mix",
                    message=f"{cue.track_id} at {cue.start_s:g}s has an unknown licence",
                    at_s=cue.start_s,
                )
            )

    audible_music = [cue for cue in design.music if cue.action != "silence"]
    if design.content_kind in {"formal_course", "news"} and audible_music:
        checks.append(
            SoundCheck(
                id="sound.bgm_policy",
                level="error",
                rule="formal courses and news carry no music bed",
                message=f"{len(audible_music)} music cues contradict content_kind={design.content_kind}",
            )
        )

    if design.content_kind == "popular_science":
        if not any(cue.action in {"duck", "silence"} for cue in design.music):
            checks.append(
                SoundCheck(
                    id="sound.music_never_rests",
                    level="warning",
                    rule="at least one section drops the music out",
                    message="every cue holds or lifts; nothing gives the explanation room",
                )
            )
        longest = _longest_run(audible_music)
        if longest > 240.0:
            checks.append(
                SoundCheck(
                    id="sound.music_continuous",
                    level="warning",
                    rule="no uninterrupted music bed longer than 4 minutes",
                    message=f"the longest continuous cue runs {longest:.0f}s",
                )
            )

    for event in design.sfx:
        if event.trigger == "visual_event" and not event.visual_ref:
            checks.append(
                SoundCheck(
                    id="sound.sfx_unmotivated",
                    level="error",
                    rule="every effect names the picture event that triggers it",
                    message=f"{event.id} claims a visual trigger but names no event",
                    at_s=event.at_s,
                )
            )
    if design.sfx and not has_visual_design:
        checks.append(
            SoundCheck(
                id="sound.sfx_unverified",
                level="warning",
                rule="effects are verified against a visual design",
                message="effects exist but there is no visual_design.json for this lesson; run visual-design first",
            )
        )

    events = sorted(event.at_s for event in design.sfx)
    if events:
        density = _window_density(events)
        if density > 4:
            checks.append(
                SoundCheck(
                    id="sound.sfx_density",
                    level="warning",
                    rule="at most 4 effects in any 20 s",
                    message=f"{density} effects fall inside one 20 s window; this reads as game UI",
                    at_s=events[0],
                )
            )

    if design.ambience and design.content_kind == "formal_course":
        checks.append(
            SoundCheck(
                id="sound.ambience_in_lecture",
                level="warning",
                rule="ambience in a lecture is a deliberate decision",
                message=f"{len(design.ambience)} ambience cues in a formal course; confirm each one belongs",
            )
        )

    if design.mix.loudness_lufs < -17.0 or design.mix.loudness_lufs > -15.0:
        checks.append(
            SoundCheck(
                id="sound.loudness_target",
                level="warning",
                rule="delivery target is -16 LUFS stereo (±1)",
                message=f"planned loudness is {design.mix.loudness_lufs:g} LUFS",
            )
        )
    if design.mix.true_peak_db > -1.0:
        checks.append(
            SoundCheck(
                id="sound.true_peak",
                level="warning",
                rule="true peak stays at or below -1 dBTP",
                message=f"planned true peak is {design.mix.true_peak_db:g} dBTP",
            )
        )

    if design.voice:
        deliveries = {cue.delivery for cue in design.voice}
        span = max(cue.at_s for cue in design.voice) - min(cue.at_s for cue in design.voice)
        if len(deliveries) == 1 and span > 300.0:
            checks.append(
                SoundCheck(
                    id="sound.voice_monotone",
                    level="warning",
                    rule="delivery changes with the function of the paragraph",
                    message=f"{len(design.voice)} segments over {span:.0f}s all use {deliveries.pop()}",
                )
            )

    return checks
