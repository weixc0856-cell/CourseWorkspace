"""Direct Offline VoxCPM2 Synthesizer for T1-01 Narration
Directly targets Content Root: D:/CourseContent/build/t1-01-why-aerodynamics.
Loads model directly in memory, synthesizes all 33 segments from narration-for-tts.json,
concatenates them into a broadcast-grade narration_full.wav, emits bilingual SRT,
and saves timeline_metadata.json for video assembly.

Requires BypassSandbox: true for loading PyTorch DLLs and weights from D:/AI.
"""
from __future__ import annotations
import json
import os
import sys
import time
import wave
from pathlib import Path
import numpy as np

CONTENT_ROOT = Path(r"D:\CourseContent")
LESSON_SLUG = "t1-01-why-aerodynamics"
BUILD_DIR = CONTENT_ROOT / "build" / LESSON_SLUG

JSON_PATH = BUILD_DIR / "narration" / "narration-for-tts.json"
AUDIO_OUT_DIR = BUILD_DIR / "audio"
AUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = Path(r"D:\AI\models\voxcpm2")
VOICE_REF = CONTENT_ROOT / "audio" / "voice" / "my_voice_en_ref_short.wav"
SRT_PATH = BUILD_DIR / "subtitles" / "t1-01-narration-en-zh.srt"
SRT_PATH.parent.mkdir(parents=True, exist_ok=True)
FULL_WAV_PATH = AUDIO_OUT_DIR / "narration_full.wav"
TIMELINE_META_PATH = AUDIO_OUT_DIR / "timeline_metadata.json"

def format_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, r = divmod(ms, 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def run_synthesis(limit: int | None = None):
    print("=" * 60)
    print("VoxCPM2 Direct Synthesizer · Direct to Content Root")
    print(f"Target Build Dir: {BUILD_DIR}")
    print(f"Model           : {MODEL_DIR}")
    print(f"Voice Reference : {VOICE_REF}")
    print("=" * 60)
    
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        segments = json.load(f)
        
    if limit:
        segments = segments[:limit]
        print(f"[Smoke Run] Processing first {limit} segments only.")
        
    os.environ["VOX_MODEL_DIR"] = str(MODEL_DIR)
    os.environ["VOX_DEVICE"] = "cpu"
    os.environ["VOX_CPU_THREADS"] = "12"
    
    import torch
    torch.set_num_threads(12)
    from voxcpm import VoxCPM
    
    print("[1/3] Loading VoxCPM2 weights into CPU memory...")
    t0 = time.time()
    model = VoxCPM.from_pretrained(
        str(MODEL_DIR),
        load_denoiser=False,
        device="cpu",
        optimize=False
    )
    print(f"[1/3] Model loaded successfully in {time.time() - t0:.2f}s!")
    
    sample_rate = 48000
    
    srt_entries = []
    timeline_shots = []
    current_timeline_sec = 0.6  # 0.6s lead in
    all_audio_chunks = []
    
    lead_silence = np.zeros(int(current_timeline_sec * sample_rate), dtype=np.int16)
    all_audio_chunks.append(lead_silence)
    
    print(f"[2/3] Processing {len(segments)} segments...")
    
    for idx, seg in enumerate(segments):
        slide = seg["slide"]
        step = seg["step"]
        en_text = seg["en"]
        tts_text = seg.get("tts_text", en_text)
        zh_text = seg["zh"]
        seg_id = f"slide-{slide:02d}-step-{step}"
        shot_id = f"shot-{slide:02d}-step-{step}"
        out_wav = AUDIO_OUT_DIR / f"{seg_id}.wav"
        
        # Incremental cache check in Content Root audio/
        if out_wav.exists() and out_wav.stat().st_size > 1024:
            print(f"  [{idx+1}/{len(segments)}] {seg_id} ... cached in Content Root, skipping synthesis.")
            with wave.open(str(out_wav), "rb") as wf:
                dur_sec = wf.getnframes() / wf.getframerate()
                raw_bytes = wf.readframes(wf.getnframes())
                audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        else:
            print(f"  [{idx+1}/{len(segments)}] {seg_id} ... synthesizing...", end=" ", flush=True)
            t_start = time.time()
            
            audio_float = model.generate(
                text=tts_text,
                prompt_wav_path=None,
                prompt_text=None,
                reference_wav_path=str(VOICE_REF),
                cfg_value=2.0,
                inference_timesteps=10,
                max_len=4096,
                normalize=True
            )
            
            audio_float = np.clip(audio_float, -1.0, 1.0)
            audio_int16 = (audio_float * 32767.0).astype(np.int16)
            
            with wave.open(str(out_wav), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
                
            dur_sec = len(audio_int16) / sample_rate
            t_synth = time.time() - t_start
            print(f"Done ({dur_sec:.2f}s audio in {t_synth:.2f}s)")
        
        all_audio_chunks.append(audio_int16)
        
        srt_start = current_timeline_sec
        srt_end = srt_start + dur_sec
        srt_entries.append((len(srt_entries) + 1, srt_start, srt_end, en_text, zh_text))
        
        gap_sec = 0.8 if step == 3 else 0.4
        gap_silence = np.zeros(int(gap_sec * sample_rate), dtype=np.int16)
        all_audio_chunks.append(gap_silence)
        
        shot_total_duration = dur_sec + gap_sec
        timeline_shots.append({
            "shot_id": shot_id,
            "slide": slide,
            "step": step,
            "audio_file": f"audio/{seg_id}.wav",
            "image_file": f"shots/{shot_id}.png",
            "start_time_s": round(srt_start, 3),
            "end_time_s": round(srt_end, 3),
            "shot_duration_s": round(shot_total_duration, 3),
            "en": en_text,
            "zh": zh_text
        })
        
        current_timeline_sec = srt_end + gap_sec
        
        # Save intermediate timeline metadata directly in Content Root
        with open(TIMELINE_META_PATH, "w", encoding="utf-8") as f_meta:
            json.dump({
                "total_shots": len(timeline_shots),
                "current_duration_s": round(current_timeline_sec, 3),
                "shots": timeline_shots
            }, f_meta, indent=2, ensure_ascii=False)

    print("[3/3] Assembling narration_full.wav and subtitles in Content Root...")
    full_audio = np.concatenate(all_audio_chunks)
    with wave.open(str(FULL_WAV_PATH), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(full_audio.tobytes())
        
    total_dur = len(full_audio) / sample_rate
    print(f"[Done] narration_full.wav created: {total_dur:.2f}s ({total_dur/60:.2f} min)")
    
    with open(SRT_PATH, "w", encoding="utf-8") as srt_f:
        for num, st, ed, en, zh in srt_entries:
            srt_f.write(f"{num}\n")
            srt_f.write(f"{format_srt_time(st)} --> {format_srt_time(ed)}\n")
            srt_f.write(f"{en}\n{zh}\n\n")
            
    print(f"[Done] Subtitle created: {SRT_PATH}")
    print(f"[Done] Timeline metadata created: {TIMELINE_META_PATH}")

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_synthesis(lim)
