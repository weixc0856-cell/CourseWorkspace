from __future__ import annotations

import json

import typer

from pathlib import Path

from course_control.content.paths import ContractError, LessonPaths

from . import app
from course_control.cli._common import _paths, _authoring_client, _lesson_path
from course_control.platform.workspace_layout import build_root_for, runtime_root


@app.command("tts-status")
def tts_status_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    port: int = typer.Option(50000, "--port"),
) -> None:
    """Show VoxCPM health, port owner and lock holder."""
    from ai_runtime.locks import FileLock

    from course_control.voice.narrate import health, load_local_paths, port_owner

    workspace = workspace.resolve()
    config = load_local_paths(workspace)
    base = f"http://127.0.0.1:{port}"
    payload = health(base)
    owner = port_owner(port)
    info = FileLock(runtime_root(workspace) / "locks" / f"tts-{port}.lock").read()
    typer.echo(f"TTS {port}: {(payload or {}).get('status', 'down')}")
    if payload:
        typer.echo(
            f"model: {payload.get('model', 'unknown')}, "
            f"sample_rate: {payload.get('sample_rate', 'unknown')}"
        )
    if owner:
        typer.echo(f"port owner: {owner['process']} pid={owner['pid']}")
    else:
        typer.echo("port owner: none")
    if info:
        typer.echo(
            f"lock: task={info.task_id} pid={info.pid} since={info.created_at}"
        )
    else:
        typer.echo("lock: free")


@app.command("narrate")
def narrate_command(
    lesson: str = typer.Option(..., "--lesson"),
    segment_id: str = typer.Option(..., "--segment-id"),
    text: str | None = typer.Option(None, "--text"),
    text_file: Path | None = typer.Option(None, "--text-file"),
    voice_ref: Path | None = typer.Option(None, "--voice-ref"),
    prompt_text: str | None = typer.Option(None, "--prompt-text"),
    prompt_text_file: Path | None = typer.Option(None, "--prompt-text-file"),
    mode: str = typer.Option("prompt_reference", "--mode"),
    style: str | None = typer.Option(None, "--style"),
    reference_wav: Path | None = typer.Option(None, "--reference-wav"),
    text_frontend: bool = typer.Option(True, "--text-frontend/--no-text-frontend"),
    output: Path | None = typer.Option(None, "--out"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    runtime_dir: Path | None = typer.Option(None, "--runtime-dir"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    force: bool = typer.Option(False, "--force"),
    speed: float = typer.Option(1.0, "--speed"),
    wait_timeout_s: int = typer.Option(1800, "--wait-timeout-s"),
) -> None:
    """Synthesize one narration segment with VoxCPM2 (V1)."""
    from course_control.voice.narrate import (
        TtsError,
        TtsService,
        load_local_paths,
        segment_cache_key,
        synthesize,
    )

    workspace = workspace.resolve()
    config = load_local_paths(workspace)
    tts = config.get("tts") or {}
    ai_root = Path(config.get("ai_root") or "").resolve()
    runtime = runtime_dir or Path(tts.get("runtime_dir") or (ai_root / "VoxCPM-Runtime"))
    if text is None:
        if text_file is None:
            typer.echo("provide --text or --text-file", err=True)
            raise typer.Exit(2)
        text = text_file.read_text(encoding="utf-8")
    if voice_ref is None:
        value = tts.get("voice_ref_en") or tts.get("voice_ref")
        if not value:
            typer.echo("provide --voice-ref or config tts.voice_ref", err=True)
            raise typer.Exit(2)
        voice_ref = Path(value)
    reference_wav = reference_wav or voice_ref
    if prompt_text is None:
        if prompt_text_file is not None:
            prompt_text = prompt_text_file.read_text(encoding="utf-8").strip()
        else:
            default_prompt = (
                tts.get("prompt_text_en")
                if tts.get("voice_ref_en")
                else tts.get("prompt_text")
            )
            prompt_text = str(default_prompt or "").strip() or None
    output = output or (
        build_root_for(workspace, lesson) / "narration" / "segments" / f"{segment_id}.wav"
    )
    meta_path = output.with_suffix(".meta.json")
    key = segment_cache_key(
        text,
        voice_ref,
        prompt_text or "",
        mode=mode,
        style=style,
        speed=speed,
        text_frontend=text_frontend,
    )
    if not force and output.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("cache_key") == key:
            typer.echo(f"cache hit: {output}")
            raise typer.Exit(0)

    log_path = build_root_for(workspace, lesson) / "narration" / "tts-server.log"
    try:
        with TtsService(
            workspace,
            ai_root=ai_root,
            runtime_dir=runtime,
            log_path=log_path,
            start_service=start_service,
            wait_timeout_s=wait_timeout_s,
        ) as service:
            typer.echo(f"TTS 50000: ready ({service.mode})")
            details = synthesize(
                service.base_url,
                text,
                voice_ref,
                prompt_text,
                output,
                speed=speed,
                mode=mode,
                reference_wav=reference_wav,
                style=style,
                text_frontend=text_frontend,
            )
    except TtsError as exc:
        typer.echo(f"TTS error: {exc}", err=True)
        raise typer.Exit(1)
    meta = {
        "schema_version": 1,
        "lesson": lesson,
        "segment_id": segment_id,
        "text_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
        "voice_ref": str(voice_ref),
        "voice_ref_sha256": __import__("hashlib").sha256(voice_ref.read_bytes()).hexdigest(),
        "prompt_text_sha256": __import__("hashlib").sha256(
            (prompt_text or "").encode("utf-8")
        ).hexdigest(),
        "cache_key": key,
        "cache_hit": False,
        "model": "VoxCPM2",
        "timesteps": 10,
        "speed": speed,
        "mode": mode,
        "style": style,
        "reference_wav": str(reference_wav),
        "text_frontend": text_frontend,
        "output": str(output),
        **details,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    typer.echo(
        f"wrote {output} ({details['audio_seconds']:.3f}s audio, "
        f"{details['synth_seconds']:.1f}s synth)"
    )


@app.command("narration-assets")
def narration_assets_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    show_text: bool = typer.Option(
        False, "--show-text", help="Print every segment after lexicon substitution"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show the Voice Bible and Lexicon a lesson resolves to, and check them."""
    from course_control.voice.audio import AudioAssetError, resolve_assets
    from course_control.authoring.models import NarrationScript

    workspace = workspace.resolve()
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        assets = resolve_assets(workspace, paths.lesson)
    except AudioAssetError as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)

    payload = assets.as_dict()
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        bible = payload["voice_bible"]
        if bible is None:
            typer.echo("voice bible: none (config tts.voice_ref*)")
        else:
            typer.echo(f"voice bible: {bible['id']}  sha256 {bible['sha256'][:12]}…")
            typer.echo(f"  ref audio: {bible['ref_audio']}")
            typer.echo(f"  model: {bible['model']} / {bible['backend']} / {bible['language']}")
        lexicon = payload["lexicon"]
        if lexicon is None:
            typer.echo("lexicon: none")
        else:
            typer.echo(
                f"lexicon: {lexicon['id']}  sha256 {lexicon['sha256'][:12]}…  "
                f"{lexicon['entries']} entries"
            )
        for problem in payload["problems"]:
            typer.echo(f"  problem: {problem}", err=True)

    if show_text:
        script_rel = paths.lesson.authoring.script if paths.lesson.authoring else None
        if not script_rel:
            typer.echo("lesson declares no authoring script", err=True)
            raise typer.Exit(1)
        script = NarrationScript.model_validate(
            json.loads(paths.content_path(script_rel).read_text(encoding="utf-8"))
        )
        changed = 0
        for page in script.pages:
            for segment in page.segments:
                application = assets.apply(segment.text)
                if application.changed:
                    changed += 1
                    pairs = ", ".join(f"{term} -> {say}" for term, say in application.applied)
                    typer.echo(f"[{segment.id}] {pairs}")
                    typer.echo(f"    {application.text}")
        typer.echo(f"segments rewritten by the lexicon: {changed}")

    raise typer.Exit(1 if payload["problems"] else 0)


@app.command("subtitles-build")
def subtitles_build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    glossary: Path | None = typer.Option(None, "--glossary"),
    planned: bool = typer.Option(False, "--planned"),
    strict: bool = typer.Option(True, "--strict/--no-strict"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Build a bilingual subtitle draft from measured narration."""
    from course_control.authoring.models import NarrationScript
    from course_control.authoring.pipeline import assert_approved
    from course_control.voice.subtitles import SubtitleBlocked, SubtitleError, build_subtitles

    workspace = workspace.resolve()
    root = _lesson_path(workspace, lesson_dir, lesson)
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    script_relative = (
        paths.lesson.authoring.script
        if paths.lesson.authoring and paths.lesson.authoring.script
        else "authoring/narration.script.json"
    )
    script_path = root / script_relative
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not script_path.is_file() or (not planned and not meta_path.is_file()):
        typer.echo("approved script and narration.meta.json are required (or use --planned)", err=True)
        raise typer.Exit(1)
    script = NarrationScript.model_validate(
        json.loads(script_path.read_text(encoding="utf-8"))
    )
    meta = None if planned else json.loads(meta_path.read_text(encoding="utf-8"))
    if meta is not None:
        from course_control.platform.media import sha256_file

        recorded = (meta.get("source") or {}).get("script_sha256")
        current = sha256_file(script_path)
        if recorded and recorded != current:
            typer.echo(
                "blocked: the narration was built from a different script "
                f"({recorded[:12]}… vs {current[:12]}…); re-run narration-build first",
                err=True,
            )
            raise typer.Exit(3)
    try:
        if not planned:
            assert_approved(root, script_relative)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            draft, srt_path = build_subtitles(
                workspace, paths, script, meta, client,
                glossary_path=glossary, strict=(strict and not planned),
            )
    except SubtitleBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (SubtitleError, Exception) as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"cues: {len(draft.cues)}")
    if draft.counts.get("problems"):
        typer.echo(f"warnings: {draft.counts['problems']} cue policy issues (planned draft)")
    typer.echo(f"draft: {srt_path}")

    # Subtitle QC runs immediately after the draft is written: a subtitle that
    # cannot pass QC must not reach composition (P5 lesson 1).
    from course_control.platform.media import sha256_file
    from course_control.voice.subtitles_qc import check_srt

    qc = check_srt(
        srt_path,
        bilingual=paths.lesson.subtitles.bilingual,
        glossary_path=glossary or root / "authoring" / "glossary.yaml",
    )
    qc["source"] = {"path": str(srt_path), "sha256": sha256_file(srt_path)}
    qc_path = paths.build_root / "quality" / "subtitles-qc.json"
    qc_path.parent.mkdir(parents=True, exist_ok=True)
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"qc: {qc['status']} ({qc_path})")
    for item in qc["errors"][:6]:
        typer.echo(f"  [error] {item}", err=True)
    if qc["status"] == "FAIL" and not planned:
        raise typer.Exit(1)


@app.command("subtitles-rewrap")
def subtitles_rewrap_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    write: bool = typer.Option(False, "--write", help="write the rewrapped SRT"),
    draft: bool = typer.Option(False, "--draft", help="rewrap build/subtitles/bilingual.draft.json"),
) -> None:
    """Rewrap subtitle lines at word/punctuation boundaries without changing text."""
    from course_control.voice.subtitles import (
        BilingualDraft,
        CuePolicy,
        rewrap_draft,
        rewrap_srt,
        validate_cues,
        write_srt,
        write_vtt,
    )

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if draft:
        draft_path = paths.build_root / "subtitles" / "bilingual.draft.json"
        if not draft_path.is_file():
            typer.echo(f"subtitle draft not found: {draft_path}", err=True)
            raise typer.Exit(1)
        original = BilingualDraft.model_validate(
            json.loads(draft_path.read_text(encoding="utf-8"))
        )
        updated = rewrap_draft(original, CuePolicy(), float(paths.lesson.outputs.fps))
        total_ms = max((cue.end_ms for cue in updated.cues), default=0)
        problems = validate_cues(
            [cue.model_dump(mode="json") for cue in updated.cues],
            CuePolicy(),
            float(paths.lesson.outputs.fps),
            total_ms,
        )
        typer.echo(f"source: {draft_path}")
        typer.echo(f"cues: {len(original.cues)} -> {len(updated.cues)}")
        for problem in problems:
            typer.echo(f"  [problem] {problem}", err=True)
        if write:
            draft_path.write_text(
                json.dumps(updated.model_dump(mode="json"), ensure_ascii=False, indent=2)
                + chr(10),
                encoding="utf-8",
            )
            write_srt(
                [cue.model_dump(mode="json") for cue in updated.cues],
                draft_path.with_suffix(".srt"),
            )
            write_vtt(
                [cue.model_dump(mode="json") for cue in updated.cues],
                draft_path.with_suffix(".vtt"),
            )
            typer.echo(f"wrote: {draft_path}")
        raise typer.Exit(0 if not problems else 1)
    target = paths.subtitles_path()
    if target is None or not target.is_file():
        target = paths.build_root / "subtitles" / "bilingual.draft.srt"
    if not target.is_file():
        typer.echo(f"subtitle SRT not found: {target}", err=True)
        raise typer.Exit(1)
    original = target.read_text(encoding="utf-8", errors="replace")
    rewrapped = rewrap_srt(
        original, CuePolicy(), bilingual=paths.lesson.subtitles.bilingual
    )
    before = len(original.splitlines())
    after = len(rewrapped.splitlines())
    typer.echo(f"source: {target}")
    typer.echo(f"lines: {before} -> {after}")
    if write:
        target.write_text(rewrapped, encoding="utf-8")
        typer.echo(f"wrote: {target}")
    else:
        typer.echo(rewrapped[:2000])
    raise typer.Exit(0)


@app.command("subtitles-accept")
def subtitles_accept_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Human gate: promote the bilingual draft into lessons/<slug>/subtitles.srt."""
    from course_control.voice.subtitles import SubtitleError, accept_subtitles

    workspace = workspace.resolve()
    root = _lesson_path(workspace, lesson_dir, lesson)
    try:
        paths = LessonPaths.load(workspace, root)
        target = accept_subtitles(workspace, paths)
    except (ContractError, SubtitleError, Exception) as exc:  # noqa: BLE001
        typer.echo(f"accept failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"accepted: {target}")


@app.command("burn-subs")
def burn_subs_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    encoder: str = typer.Option("auto", "--encoder"),
) -> None:
    """Burn the generated ASS subtitles onto the clean master."""
    from course_control.rendering.adapters.burn import burn_subtitles

    workspace = workspace.resolve()
    root = _lesson_path(workspace, lesson_dir, lesson)
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if encoder not in ("auto", "qsv", "libx264"):
        typer.echo("--encoder must be auto, qsv or libx264", err=True)
        raise typer.Exit(2)
    outcome = burn_subtitles(paths, encoder=encoder)
    for output in outcome.outputs:
        typer.echo(f"output: {output}")
    for warning in outcome.warnings:
        typer.echo(f"warning: {warning}")
    for error in outcome.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"status: {outcome.status.value}")
    raise typer.Exit(0 if outcome.status.value == "pass" else 1)


@app.command("subtitles-qc")
def subtitles_qc_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    file: Path | None = typer.Option(None, "--file", help="audit this SRT instead"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Audit subtitle timing, language, line breaks and glossary terms."""
    from course_control.voice.subtitles_qc import check_srt

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    target = file or paths.subtitles_path()
    if target is None or not target.is_file():
        typer.echo("no subtitle file to audit", err=True)
        raise typer.Exit(1)
    report = check_srt(
        target,
        bilingual=paths.lesson.subtitles.bilingual,
        glossary_path=paths.lesson_dir / "authoring" / "glossary.yaml",
    )
    from course_control.platform.media import sha256_file

    report["source"] = {"path": str(target), "sha256": sha256_file(target)}
    out = paths.build_root / "quality" / "subtitles-qc.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"status: {report['status']}  cues: {report['cues']}")
        for item in report["errors"]:
            typer.echo(f"  [error] {item}")
        for item in report["warnings"]:
            typer.echo(f"  [warn] {item}")
        typer.echo(f"report: {out}")
    raise typer.Exit(1 if report["status"] == "FAIL" else 0)


@app.command("audio-plan")
def audio_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate the content-kind/BGM policy and write audio_plan.json."""
    from course_control.voice.audio_plan import write_audio_plan

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    plan, target = write_audio_plan(paths.build_root, paths.lesson)
    typer.echo(f"content_kind: {plan.content_kind}")
    typer.echo(f"bgm_allowed: {plan.bgm_allowed}")
    typer.echo(f"cues: {len(plan.cues)}")
    for warning in plan.warnings:
        typer.echo(f"warning: {warning}")
    for error in plan.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"audio_plan: {target}")
    raise typer.Exit(0 if plan.status == "ready" else 2)


@app.command("audio-mix")
def audio_mix_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Mix the planned BGM bed into the finished video with ducking."""
    from course_control.voice.audio_mix import mix_lesson

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    result = mix_lesson(workspace.resolve(), paths)
    typer.echo(f"status: {result.status.value}")
    if result.output is not None:
        typer.echo(f"output: {result.output}")
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for error in result.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"report: {result.report_path}")
    raise typer.Exit(0 if result.status.value in {"pass", "skipped"} else 1)


@app.command("media-qc")
def media_qc_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run full-file audio/video/subtitle checks on the finished video."""
    from course_control.quality.media_qc import BLOCKED, INCOMPLETE, run_media_qc

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = run_media_qc(workspace.resolve(), paths)
    typer.echo(f"status: {report['status']}")
    for check in report["checks"]:
        typer.echo(f"  [{check['id']}] {check['status']}: {check['detail']}")
    typer.echo(f"report: {target}")
    if report["status"] == BLOCKED:
        raise typer.Exit(1)
    if report["status"] == INCOMPLETE:
        raise typer.Exit(3)
    raise typer.Exit(0)


@app.command("quality-report")
def quality_report_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Aggregate the five quality dimensions from existing artifacts."""
    from course_control.quality.quality import BLOCKED, INCOMPLETE, build_quality_report

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = build_quality_report(workspace.resolve(), paths)
    for item in report["dimensions"]:
        typer.echo(f"  [{item['id']}] {item['status']}: {item['reason']}")
    states = report["states"]
    for key in (
        "BUILD_PASS",
        "VERIFY_PASS",
        "VERIFY_INCOMPLETE",
        "VERIFY_FAIL",
        "QUALITY_PASS",
        "QUALITY_VERIFIED",
        "REVIEW_APPROVED",
        "RELEASE_APPROVED",
    ):
        typer.echo(f"{key}: {states[key]}")
    typer.echo(f"report: {target}")
    if any(item["status"] == BLOCKED for item in report["dimensions"]):
        raise typer.Exit(1)
    if any(item["status"] == INCOMPLETE for item in report["dimensions"]):
        raise typer.Exit(3)
    raise typer.Exit(0)


@app.command("asr-align")
def asr_align_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    model: str = typer.Option("small.en", "--model"),
    language: str = typer.Option("en", "--language"),
    device: str = typer.Option("cpu", "--device"),
    compute_type: str = typer.Option("int8", "--compute-type"),
) -> None:
    """Transcribe narration with ASR and check subtitle/speech agreement."""
    from course_control.voice.alignment import BLOCKED, INCOMPLETE, run_alignment

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = run_alignment(
        workspace.resolve(),
        paths,
        model_size=model,
        language=language,
        device=device,
        compute_type=compute_type,
    )
    typer.echo(f"status: {report['status']}")
    typer.echo(f"cues: {report.get('cue_count', 0)}  words: {report.get('word_count', 0)}")
    typer.echo(f"mean coverage: {report.get('mean_coverage', 0)}")
    for mismatch in report.get("mismatches", [])[:8]:
        typer.echo(
            f"  cue {mismatch['index']}: coverage {mismatch['coverage']} "
            f"({mismatch['start_ms']}–{mismatch['end_ms']} ms)"
        )
    for interval in report.get("uncovered_speech", [])[:8]:
        typer.echo(
            f"  uncovered {interval['start_s']}–{interval['end_s']}s: {interval['text'][:80]}"
        )
    for error in report.get("errors", []):
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"report: {target}")
    if report["status"] == BLOCKED:
        raise typer.Exit(1)
    if report["status"] == INCOMPLETE:
        raise typer.Exit(3)
    raise typer.Exit(0)
