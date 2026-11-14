"""Preview/release orchestration for one lesson.

The runner chooses the cheapest unit that can answer the question:

* ``shot``    - one engine shot or one Remotion window
* ``segment`` - one contiguous group, rendered as one Remotion window
* ``project`` - the whole film, rendered at preview scale

Release mode delegates to the existing build pipeline instead of reimplementing
it.  Nothing here writes into ``deliver/``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.preview.engines import EngineResult, render_engine_shot
from course_control.preview.profile import PreviewLevel, PreviewProfile, RenderMode
from course_control.preview.remotion_window import WindowResult, render_lesson_window
from course_control.preview.units import PreviewUnit, plan_lesson_units, segments


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _result_row(result: EngineResult | WindowResult, unit: PreviewUnit | None = None) -> dict:
    row = {
        "unit": result.unit_id,
        "status": result.status,
        "output": str(result.path) if result.path else None,
        "duration_ms": result.duration_ms,
        "key": result.key,
        "warnings": result.warnings or [],
        "detail": result.detail,
    }
    if hasattr(result, "frames"):
        row["frames"] = result.frames
    if unit is not None:
        row["kind"] = unit.kind
        row["engine"] = unit.engine
        row["segment"] = unit.segment
        row["design"] = unit.design is not None
    return row


def _write_report(
    build_root: Path, payload: dict, name: str = "report.json", mode: str = "preview"
) -> Path:
    out = build_root / mode
    out.mkdir(parents=True, exist_ok=True)
    target = out / name
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _contact_sheet(path: Path, workspace: Path) -> Path | None:
    try:
        from course_control.quality.code_video_qc import contact_sheet

        target = path.with_suffix(".sheet.jpg")
        return contact_sheet(path, target, step=2.0, workspace=workspace)
    except Exception:  # noqa: BLE001 - a missing thumbnail must not fail a preview
        return None


def _render_shot_units(
    paths: LessonPaths,
    units: list[PreviewUnit],
    profile: PreviewProfile,
    *,
    force: bool,
    output_root: Path | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for unit in units:
        if unit.kind == "engine":
            result = render_engine_shot(
                paths, unit, profile, force=force, output_root=output_root
            )
        else:
            result = render_lesson_window(
                paths,
                unit_id=unit.id,
                start_s=unit.start_s,
                end_s=unit.end_s,
                profile=profile,
                composition=unit.composition or "CourseTimeline",
                entry=unit.entry or "src/index.ts",
                force=force,
                output_dir=output_root,
            )
        row = _result_row(result, unit)
        if result.path is not None:
            sheet = _contact_sheet(result.path, paths.workspace)
            if sheet is not None:
                row["contact_sheet"] = str(sheet)
        rows.append(row)
    return rows


def _total_duration(paths: LessonPaths, units: list[PreviewUnit]) -> float:
    timeline = paths.build_root / "contracts" / "timeline.spec.json"
    if timeline.is_file():
        try:
            data = json.loads(timeline.read_text(encoding="utf-8"))
            fps = (data.get("fps") or {}).get("fps_num") or paths.lesson.outputs.fps
            frames = data.get("total_frames")
            if frames and fps:
                return float(frames) / float(fps)
        except (OSError, ValueError, TypeError):
            pass
    shots = paths.build_root / "shots.json"
    if shots.is_file():
        try:
            data = json.loads(shots.read_text(encoding="utf-8"))
            total = (data.get("timeline") or {}).get("total_duration_s")
            if total:
                return float(total)
        except (OSError, ValueError, TypeError):
            pass
    return max((unit.end_s for unit in units), default=0.0)


def _render_window_groups(
    paths: LessonPaths,
    groups: dict[str, list[PreviewUnit]],
    profile: PreviewProfile,
    level: PreviewLevel,
    *,
    force: bool,
    output_root: Path | None = None,
    bounds: tuple[float, float] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for group_id, group_units in groups.items():
        if bounds is not None:
            start, end = bounds
        else:
            start = min(unit.start_s for unit in group_units)
            end = max(unit.end_s for unit in group_units)
        composition = group_units[0].composition or "CourseTimeline"
        entry = group_units[0].entry or "src/index.ts"
        result = render_lesson_window(
            paths,
            unit_id=group_id,
            start_s=start,
            end_s=end,
            profile=profile,
            composition=composition,
            entry=entry,
            force=force,
            output_dir=output_root,
        )
        row = _result_row(result)
        row["units"] = [unit.id for unit in group_units]
        row["start_s"] = round(start, 3)
        row["end_s"] = round(end, 3)
        row["level"] = level.value
        if result.path is not None:
            sheet = _contact_sheet(result.path, paths.workspace)
            if sheet is not None:
                row["contact_sheet"] = str(sheet)
        rows.append(row)
    return rows


def run_preview(
    paths: LessonPaths,
    *,
    level: PreviewLevel | str,
    profile: PreviewProfile,
    selection: set[str] | None = None,
    force: bool = False,
    output_root: Path | None = None,
) -> dict:
    """Render a preview and write ``preview/report.json``.

    A failed unit is reported, not hidden.  The run is ``ok`` only when every
    selected unit exists and rendered (or was reused from a matching cache).
    """
    level = PreviewLevel(level)
    started = time.monotonic()
    units = plan_lesson_units(paths, level, selection)
    if not units:
        raise ValueError(
            "no preview units matched; check --shot/--segment ids or run collect first"
        )
    if level is PreviewLevel.SHOT:
        rows = _render_shot_units(
            paths, units, profile, force=force, output_root=output_root
        )
        scope = "shot"
    elif level is PreviewLevel.SEGMENT:
        groups = segments(units)
        rows = _render_window_groups(
            paths, groups, profile, level, force=force, output_root=output_root
        )
        scope = "segment"
    else:
        groups = {"project": units}
        rows = _render_window_groups(
            paths,
            groups,
            profile,
            level,
            force=force,
            output_root=output_root,
            bounds=(0.0, _total_duration(paths, units)),
        )
        scope = "project"

    if level is PreviewLevel.PROJECT and profile.is_preview and profile.audio and rows:
        row = rows[0]
        if row.get("output"):
            base = Path(row["output"])
            from course_control.preview.sound_mix import mix_preview

            sound, sound_warnings = mix_preview(
                paths, base, base.with_name("project-sound.mp4")
            )
            row["warnings"].extend(sound_warnings)
            if sound is not None:
                row["output"] = str(sound)
                row["sound_design"] = True
            else:
                from course_control.preview.audio import mix_music, resolve_music

                music = resolve_music(paths)
                if music is not None:
                    mixed, error = mix_music(
                        paths.workspace,
                        base,
                        music,
                        base.with_name("project-mixed.mp4"),
                    )
                    if mixed is not None:
                        row["output"] = str(mixed)
                        row["music"] = str(music)
                    else:
                        row["warnings"].append(error or "preview music mix failed")

    failed = [row for row in rows if row["status"] == "failed"]
    cached = [row for row in rows if row["status"] == "cached"]
    payload = {
        "schema_version": 1,
        "kind": "preview_report" if profile.is_preview else "render_report",
        "lesson": paths.slug,
        "mode": profile.mode.value,
        "level": level.value,
        "scope": scope,
        "generated_at": _now(),
        "profile": profile.as_dict(),
        "units": rows,
        "totals": {
            "units": len(rows),
            "ok": len(rows) - len(failed) - len(cached),
            "cached": len(cached),
            "failed": len(failed),
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
        "delivery_allowed": False if profile.is_preview else None,
        "ok": not failed,
    }
    mode_name = "preview" if profile.is_preview else "release"
    report = _write_report(paths.build_root, payload, mode=mode_name)
    payload["report"] = str(report)
    _write_report(paths.build_root, payload, "manifest.json", mode=mode_name)
    return payload


def run_pilot(paths: LessonPaths, *, profile: PreviewProfile, force: bool = False) -> dict:
    """Run P0, P1 and P2 in order and record what each level cost.

    This is the measurement harness for a real episode.  It does not decide
    whether a level was "enough"; a human reads the previews and decides.
    """
    levels = [PreviewLevel.SHOT, PreviewLevel.SEGMENT, PreviewLevel.PROJECT]
    results: dict[str, dict] = {}
    for level in levels:
        payload = run_preview(paths, level=level, profile=profile, force=force)
        results[level.value] = {
            "units": payload["totals"]["units"],
            "ok": payload["totals"]["ok"],
            "cached": payload["totals"]["cached"],
            "failed": payload["totals"]["failed"],
            "duration_ms": payload["totals"]["duration_ms"],
            "report": payload.get("report"),
        }
    summary = {
        "schema_version": 1,
        "kind": "preview_pilot",
        "lesson": paths.slug,
        "profile": profile.as_dict(),
        "levels": results,
        "generated_at": _now(),
    }
    target = paths.build_root / "preview" / "pilot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    summary["report"] = str(target)
    return summary


def release_build(paths: LessonPaths, *, resume: bool = True) -> dict:
    """Run the existing release pipeline.  Preview mode never calls this."""
    from course_control.pipeline import BuildOptions, run_build

    report, report_path = run_build(
        paths.workspace,
        paths.lesson_dir,
        BuildOptions(resume=resume),
    )
    return {
        "verdict": report.verdict,
        "report": str(report_path),
        "stages": [{"name": stage.name, "status": stage.status.value} for stage in report.stages],
        "failures": list(report.failures),
    }


__all__ = ["release_build", "run_preview"]
