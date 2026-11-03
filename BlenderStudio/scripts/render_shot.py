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


def apply_overrides(task, argv):
    is_v2 = task.get("schema_version") == 2
    render = task.setdefault("render", {}) if is_v2 else task

    engine = get_arg(argv, "--engine")
    if engine:
        render["engine"] = engine

    output = get_arg(argv, "--out")
    if output:
        render["output"] = output

    fps = get_arg(argv, "--fps")
    if fps:
        try:
            render["fps"] = int(fps)
        except ValueError:
            render_common.fail("--fps must be an integer")

    resolution = get_arg(argv, "--res")
    if resolution:
        try:
            width, height = (int(part) for part in resolution.lower().split("x"))
        except ValueError:
            render_common.fail("--res must look like 1920x1080")
        render["resolution"] = [width, height]

    frames = get_arg(argv, "--frames")
    seconds = get_arg(argv, "--seconds")
    if frames:
        try:
            frame_count = int(frames)
        except ValueError:
            render_common.fail("--frames must be an integer")
    elif seconds:
        try:
            default_fps = (
                task.get("scene", {}).get("fps", 30) if is_v2 else task.get("fps", 30)
            )
            frame_count = max(1, round(float(seconds) * int(render.get("fps") or default_fps)))
        except ValueError:
            render_common.fail("--seconds must be a number")
    else:
        frame_count = None

    if frame_count is not None:
        if is_v2:
            scene = task.setdefault("scene", {})
            frame_start = int(scene.get("frame_start", 1))
            scene["frame_end"] = frame_start + frame_count - 1
            if render.get("format", "png") == "png":
                render["frame"] = frame_start
        else:
            task["frames"] = frame_count

    blend = get_arg(argv, "--blend")
    if blend:
        if is_v2:
            task["base_blend"] = blend
        else:
            task["blend"] = blend


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    task_path = get_arg(argv, "--task")
    if not task_path:
        render_common.fail("missing --task <json>")

    task = render_common.load_json(task_path)
    apply_overrides(task, argv)
    render_common.run(task)


if __name__ == "__main__":
    main()
