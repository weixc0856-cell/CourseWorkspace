import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render_common


def get_arg(argv, name, default=None):
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        render_common.fail(f"{name} requires a value")
    return argv[index + 1]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

    lesson = get_arg(argv, "--lesson")
    if not lesson:
        render_common.fail("missing --lesson <slug>")

    resolution = get_arg(argv, "--res", "1920x1080")
    try:
        width, height = (int(part) for part in resolution.lower().split("x"))
    except ValueError:
        render_common.fail("--res must look like 1920x1080")

    fps = int(get_arg(argv, "--fps", "30"))
    seconds = float(get_arg(argv, "--seconds", "5"))
    samples = int(get_arg(argv, "--samples", "8"))
    device = get_arg(argv, "--device", "CPU").upper()

    task = {
        "schema_version": 1,
        "lesson": lesson,
        "scene": "procedural_cube",
        "engine": get_arg(argv, "--engine", "BLENDER_EEVEE"),
        "device": device,
        "resolution": [width, height],
        "fps": fps,
        "frames": max(1, round(seconds * fps)),
        "samples": samples,
        "format": "mp4",
        "output": get_arg(argv, "--out", f"build/{lesson}/blender/smoke.mp4"),
        "blend": None,
    }

    render_common.run(task)


if __name__ == "__main__":
    main()
