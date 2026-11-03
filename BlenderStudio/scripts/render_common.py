import json
import os
import re
import sys
import traceback

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALLOWED_ENGINES = {"BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH"}
ALLOWED_FORMATS = {"png", "mp4"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message):
    print(f"TASK_ERROR: {message}")
    sys.exit(1)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_task(task):
    if not isinstance(task, dict):
        fail("task must be a JSON object")
    if task.get("schema_version") != 1:
        fail("schema_version must be 1")

    lesson = task.get("lesson")
    if not isinstance(lesson, str) or not SLUG_RE.match(lesson):
        fail("lesson must be a slug matching ^[a-z0-9]+(?:-[a-z0-9]+)*$")

    for key in ("output", "format", "resolution", "fps", "frames"):
        if key not in task:
            fail(f"missing required field: {key}")

    resolution = task["resolution"]
    if (
        not isinstance(resolution, list)
        or len(resolution) != 2
        or not all(_is_int(value) and value > 0 for value in resolution)
    ):
        fail("resolution must be [width, height] with positive integers")

    fps = task["fps"]
    if not _is_int(fps) or fps <= 0:
        fail("fps must be a positive integer")

    frames = task["frames"]
    if not _is_int(frames) or frames <= 0:
        fail("frames must be a positive integer")

    samples = task.get("samples", 8)
    if not _is_int(samples) or samples <= 0:
        fail("samples must be a positive integer")

    fmt = task["format"]
    if not isinstance(fmt, str) or fmt.lower() not in ALLOWED_FORMATS:
        fail(f"format must be one of: {sorted(ALLOWED_FORMATS)}")
    fmt = fmt.lower()
    if fmt == "png" and frames != 1:
        fail("png output requires frames = 1")

    engine = task.get("engine", "BLENDER_EEVEE")
    if engine not in ALLOWED_ENGINES:
        fail(f"engine must be one of: {sorted(ALLOWED_ENGINES)}")

    output = task["output"]
    if not isinstance(output, str) or not output.strip():
        fail("output must be a non-empty path")

    output_abs = os.path.abspath(output)
    allowed_root = os.path.abspath(os.path.join("build", lesson, "blender"))
    try:
        inside = os.path.commonpath([output_abs, allowed_root]) == allowed_root
    except ValueError:
        inside = False
    if not inside:
        fail(f"output must be inside build/{lesson}/blender/")

    expected_suffix = "." + fmt
    if not output_abs.lower().endswith(expected_suffix):
        fail(f"output must end with {expected_suffix}")

    blend = task.get("blend")
    if blend is not None:
        if not isinstance(blend, str) or not blend.strip():
            fail("blend must be a non-empty path or null")
        if not os.path.isfile(blend):
            fail(f"blend file not found: {blend}")

    return {
        "lesson": lesson,
        "engine": engine,
        "resolution": resolution,
        "fps": fps,
        "frames": frames,
        "samples": samples,
        "format": fmt,
        "output": output_abs,
        "blend": blend,
    }


def build_procedural_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 1))
    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, 0))
    bpy.ops.object.light_add(type="AREA", location=(4, -4, 6))
    light = bpy.context.active_object
    light.data.energy = 1200
    light.data.size = 5

    bpy.ops.object.camera_add(location=(7, -7, 5))
    camera = bpy.context.active_object
    direction = mathutils.Vector((0, 0, 1)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("BlenderStudioWorld")
        bpy.context.scene.world = world
    # Blender 5.2 warns that use_nodes will be removed in 6.0; keep for 5.2.
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        background.inputs[1].default_value = 1.0


def configure_scene(task):
    scene = bpy.context.scene
    engine = task["engine"]
    if engine == "CYCLES":
        try:
            bpy.ops.preferences.addon_enable(module="cycles")
        except Exception:
            pass
    try:
        scene.render.engine = engine
    except Exception as exc:
        fail(f"cannot set engine {engine}: {exc}")

    width, height = task["resolution"]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = task["fps"]
    scene.frame_start = 1
    scene.frame_end = task["frames"]

    if engine == "CYCLES":
        scene.cycles.samples = task["samples"]
        scene.cycles.device = "CPU"
    elif engine == "BLENDER_EEVEE":
        scene.eevee.taa_render_samples = task["samples"]

    if task["format"] == "png":
        scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
    else:
        # Blender 5.2: video formats require media_type = VIDEO first.
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "NONE"

    scene.render.filepath = task["output"]


def render_task(task):
    if task["blend"]:
        bpy.ops.wm.open_mainfile(filepath=task["blend"])
    else:
        build_procedural_scene()

    configure_scene(task)
    scene = bpy.context.scene
    os.makedirs(os.path.dirname(task["output"]), exist_ok=True)

    print(f"BLENDER_TASK_LESSON {task['lesson']}")
    print(f"BLENDER_TASK_ENGINE {scene.render.engine}")
    print(f"BLENDER_TASK_RES {scene.render.resolution_x}x{scene.render.resolution_y}")
    print(f"BLENDER_TASK_FPS {scene.render.fps}")
    print(f"BLENDER_TASK_FRAMES {task['frames']}")
    print(f"BLENDER_TASK_FORMAT {task['format']}")
    print(f"BLENDER_TASK_OUT {task['output']}")

    if task["format"] == "png":
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)

    print("BLENDER_TASK_OK")


def run(task):
    try:
        if task.get("schema_version") == 2:
            from scene_system.executor import execute as execute_scene_task

            execute_scene_task(task, cwd=os.getcwd())
            return
        validated = validate_task(task)
        render_task(validated)
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        print(f"TASK_ERROR: {exc}")
        sys.exit(1)
