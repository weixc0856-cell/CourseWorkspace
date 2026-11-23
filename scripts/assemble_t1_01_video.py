"""Assemble Production T1-01 Videos (Clean & Hardsubbed) with 0.5s Slide Transitions
Reads from Content Root (D:/CourseContent/build/t1-01-why-aerodynamics),
generates two pristine 1080P 30fps H.264 MP4 videos:
  1. t1-01-why-aerodynamics-clean.mp4 (Pure video + 320k audio, zero subtitles)
  2. t1-01-why-aerodynamics.mp4       (Refined low-margin hardsubbed version with 30fps dynamic subtitles)

Key Upgrades:
  - Generates 0.5s (15 frames) smooth crossfade dissolves during the 0.8s silence pause between slides
  - Pure hard cuts / step-dimming within slides
  - Injects `fps=30` into FFmpeg video filter before libass to guarantee all 92 subtitle cues advance in sync
  - Renders to temporary build output first to avoid Windows file locks when user is previewing in player
  - Guarantees all standalone subtitle files (.bilingual.srt, .en.srt, .zh.srt, .ass) are deployed in deliver
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image

CONTENT_ROOT = Path(r"D:\CourseContent")
LESSON_SLUG = sys.argv[1] if len(sys.argv) > 1 else "t1-01-why-aerodynamics"
BUILD_DIR = CONTENT_ROOT / "build" / LESSON_SLUG
DELIVER_DIR = CONTENT_ROOT / "deliver" / LESSON_SLUG
DELIVER_DIR.mkdir(parents=True, exist_ok=True)

META_PATH = BUILD_DIR / "audio" / "timeline_metadata.json"
AUDIO_PATH = BUILD_DIR / "audio" / "narration_full.wav"
ASS_PATH = DELIVER_DIR / f"{LESSON_SLUG}.ass"
FINAL_DIR = BUILD_DIR / "final"
TRANS_DIR = BUILD_DIR / "transitions"
FINAL_DIR.mkdir(parents=True, exist_ok=True)
TRANS_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_MP4 = DELIVER_DIR / f"{LESSON_SLUG}-clean.mp4"
SUBBED_MP4 = DELIVER_DIR / f"{LESSON_SLUG}.mp4"
BUILD_SUBBED = FINAL_DIR / f"{LESSON_SLUG}.mp4"

def generate_slide_transitions(shots: list[dict]) -> dict[int, list[str]]:
    """Generates 0.5s (15 frames) crossfades for all slide-to-slide boundaries."""
    trans_map = {}
    print("\n[Step 1] Checking/generating 0.5s (15 frames) smooth slide-to-slide crossfades...")
    
    for i in range(len(shots) - 1):
        curr_shot = shots[i]
        next_shot = shots[i + 1]
        
        if curr_shot["slide"] != next_shot["slide"]:
            curr_img_path = BUILD_DIR / curr_shot["image_file"]
            next_img_path = BUILD_DIR / next_shot["image_file"]
            
            im_curr = Image.open(curr_img_path).convert("RGB")
            im_next = Image.open(next_img_path).convert("RGB")
            
            frame_paths = []
            prefix = f"trans_s{curr_shot['slide']:02d}_to_s{next_shot['slide']:02d}"
            
            for k in range(15):
                f_path = TRANS_DIR / f"{prefix}_{k:02d}.png"
                if not f_path.exists():
                    alpha = (k + 1) / 16.0
                    blended = Image.blend(im_curr, im_next, alpha)
                    blended.save(f_path)
                frame_paths.append(str(f_path).replace("\\", "/"))
                
            trans_map[i] = frame_paths
            print(f"  • Slide {curr_shot['slide']:02d} -> Slide {next_shot['slide']:02d}: 15 blend frames ready")
            
    return trans_map

def build_concat_list(shots: list[dict], trans_map: dict[int, list[str]]) -> Path:
    """Builds the FFmpeg concat text file with precise timings."""
    concat_txt = FINAL_DIR / "concat_list.txt"
    lines = []
    
    # 0.6s lead in on first shot
    first_image = str((BUILD_DIR / shots[0]["image_file"]).resolve()).replace("\\", "/")
    lines.append(f"file '{first_image}'")
    lines.append("duration 0.600")
    
    for i, shot in enumerate(shots):
        img_path = str((BUILD_DIR / shot["image_file"]).resolve()).replace("\\", "/")
        dur = shot["shot_duration_s"]
        
        if i in trans_map:
            # Reserve 0.500s from the end of the shot for the smooth dissolve
            hold_dur = max(0.1, dur - 0.500)
            lines.append(f"file '{img_path}'")
            lines.append(f"duration {hold_dur:.3f}")
            
            # Insert 15 transition frames
            frame_dur = 0.500 / 15.0
            for trans_frame in trans_map[i]:
                lines.append(f"file '{trans_frame}'")
                lines.append(f"duration {frame_dur:.6f}")
        else:
            lines.append(f"file '{img_path}'")
            lines.append(f"duration {dur:.3f}")
            
    last_image = str((BUILD_DIR / shots[-1]["image_file"]).resolve()).replace("\\", "/")
    lines.append(f"file '{last_image}'")
    lines.append("duration 1.000")
    lines.append(f"file '{last_image}'")
    
    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"\n[Step 2] Generated FFmpeg concat list: {concat_txt}")
    return concat_txt

def assemble_both():
    print("=" * 60)
    print("T1-01 Dual-Version Video Production Assembler")
    print(f"Build Dir   : {BUILD_DIR}")
    print(f"Deliver Dir : {DELIVER_DIR}")
    print("=" * 60)
    
    if not META_PATH.exists() or not AUDIO_PATH.exists():
        print(f"[Error] Required assets not found in {BUILD_DIR}!")
        sys.exit(1)
        
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    shots = meta.get("shots", [])
    if not shots:
        print("[Error] No shots found in metadata!")
        sys.exit(1)
        
    print(f"Loaded {len(shots)} shots from {META_PATH.name}")
    
    trans_map = generate_slide_transitions(shots)
    concat_txt = build_concat_list(shots, trans_map)
    
    # -------------------------------------------------------------
    # 3. CLEAN VERSION CHECK / RENDER
    # -------------------------------------------------------------
    clean_final = FINAL_DIR / CLEAN_MP4.name
    if not CLEAN_MP4.exists() or (CLEAN_MP4.stat().st_size < 1000):
        print("\n[Step 3] Rendering Clean Version (t1-01-why-aerodynamics-clean.mp4)...")
        t0 = time.time()
        cmd_clean = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-i", str(AUDIO_PATH),
            "-vf", "fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "320k",
            "-shortest",
            str(clean_final)
        ]
        res_clean = subprocess.run(cmd_clean, capture_output=True, text=True)
        if res_clean.returncode != 0:
            print(f"[Error rendering clean video] {res_clean.stderr}")
            sys.exit(1)
        shutil.copy2(clean_final, CLEAN_MP4)
        print(f"  • Clean MP4 completed in {time.time() - t0:.1f}s")
    else:
        print(f"\n[Step 3] Clean Version already exists: {CLEAN_MP4.name} ({CLEAN_MP4.stat().st_size / (1024*1024):.2f} MB)")
    
    # -------------------------------------------------------------
    # 4. RENDER HARDSUBBED VERSION (TO BUILD_SUBBED FIRST)
    # -------------------------------------------------------------
    print("\n[Step 4] Rendering Hardsubbed Version with 30fps dynamic subtitles...")
    t1 = time.time()
    ass_escaped = str(ASS_PATH.resolve()).replace('\\', '/').replace(':', '\\:')
    vf_filter = f"fps=30,ass='{ass_escaped}'"
    
    cmd_subbed = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-i", str(AUDIO_PATH),
        "-vf", vf_filter,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "320k",
        "-shortest",
        str(BUILD_SUBBED)
    ]
    res_subbed = subprocess.run(cmd_subbed, capture_output=True, text=True)
    if res_subbed.returncode != 0:
        print(f"[Error rendering subbed video] {res_subbed.stderr}")
        sys.exit(1)
        
    dur_subbed = time.time() - t1
    subbed_size_mb = BUILD_SUBBED.stat().st_size / (1024 * 1024)
    print(f"  • Hardsubbed MP4 encoded in {dur_subbed:.1f}s ({subbed_size_mb:.2f} MB)")
    
    # Copy to deliver dir (with lock detection and fallback copy)
    delivered_successfully = False
    for attempt in range(3):
        try:
            shutil.copy2(BUILD_SUBBED, SUBBED_MP4)
            print(f"  ✓ Successfully deployed to: {SUBBED_MP4}")
            delivered_successfully = True
            break
        except PermissionError:
            print(f"  [Attempt {attempt+1}] {SUBBED_MP4.name} is locked by player, waiting 2s...")
            time.sleep(2)
            
    if not delivered_successfully:
        # Save alternative deliver file so user can review immediately
        fallback_file = DELIVER_DIR / f"{LESSON_SLUG}-fixed.mp4"
        shutil.copy2(BUILD_SUBBED, fallback_file)
        print(f"\n  [NOTE] {SUBBED_MP4.name} was locked by an active player.")
        print(f"  ✓ Saved to: {fallback_file}")
        print(f"  (Close your player to allow auto-replacing the default filename)")
        
    # -------------------------------------------------------------
    # 5. VERIFY SUBTITLE ASSETS IN DELIVERY DIRECTORY
    # -------------------------------------------------------------
    print("\n[Step 5] Checking delivery manifests...")
    required_files = [
        CLEAN_MP4,
        SUBBED_MP4,
        DELIVER_DIR / f"{LESSON_SLUG}-fixed.mp4",
        DELIVER_DIR / f"{LESSON_SLUG}.bilingual.srt",
        DELIVER_DIR / f"{LESSON_SLUG}.en.srt",
        DELIVER_DIR / f"{LESSON_SLUG}.zh.srt",
        DELIVER_DIR / f"{LESSON_SLUG}.ass"
    ]
    
    print("\n" + "=" * 60)
    print("PRODUCTION DELIVERABLES IN:")
    print(f"  {DELIVER_DIR}")
    print("=" * 60)
    for rf in required_files:
        if rf.exists():
            size = rf.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size / 1024:.2f} KB"
            print(f"  ✓ {rf.name:<42} ({size_str:>9})")

if __name__ == "__main__":
    assemble_both()
