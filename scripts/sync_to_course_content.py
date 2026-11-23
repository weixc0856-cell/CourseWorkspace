"""Live synchronization script from CourseSlides (temporary) to D:/CourseContent/build/t1-01-why-aerodynamics.

Watches CourseSlides/t1-01-why-aerodynamics/ and mirrors every new or updated file to
D:/CourseContent/build/t1-01-why-aerodynamics/ immediately, ensuring all process assets
and deliverables live strictly inside D:/CourseContent.
"""
from __future__ import annotations
import shutil
import time
from pathlib import Path

SRC_DIR = Path(r"D:\EngineeringTransition\CourseWorkspace\CourseSlides\t1-01-why-aerodynamics")
DST_DIR = Path(r"D:\CourseContent\build\t1-01-why-aerodynamics")

def sync_once() -> int:
    if not SRC_DIR.exists():
        return 0
    copied = 0
    for src_path in SRC_DIR.rglob("*"):
        if src_path.is_file():
            rel = src_path.relative_to(SRC_DIR)
            dst_path = DST_DIR / rel
            # Only copy if dst doesn't exist or src is newer / different size
            if (not dst_path.exists()) or (src_path.stat().st_mtime > dst_path.stat().st_mtime) or (src_path.stat().st_size != dst_path.stat().st_size):
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src_path, dst_path)
                    copied += 1
                except Exception as e:
                    pass
    return copied

def run_loop(interval_sec: float = 3.0):
    print("=" * 60)
    print("Live Sync to D:/CourseContent/build/t1-01-why-aerodynamics")
    print(f"Source: {SRC_DIR}")
    print(f"Target: {DST_DIR}")
    print("=" * 60)
    
    initial = sync_once()
    print(f"[Initial Sync] {initial} files copied/updated.")
    
    while True:
        c = sync_once()
        if c > 0:
            print(f"[{time.strftime('%H:%M:%S')}] Synced {c} updated files to Content Root.")
        time.sleep(interval_sec)

if __name__ == "__main__":
    run_loop()
