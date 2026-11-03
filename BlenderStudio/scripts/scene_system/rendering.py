"""Render configuration and execution."""

from __future__ import annotations

import os

import bpy

from .task_schema import TaskError


def _enable_engine(engine):
    if engine == "CYCLES":
        try:
            bpy.ops.preferences.addon_enable(module="cycles")
        except Exception:
            pass


def configure(scene, render):
    engine = render["engine"]
    _enable_engine(engine)
    try:
        scene.render.engine = engine
    except Exception as exc:  # noqa: BLE001 - surface the Blender message
        raise TaskError(f"cannot set engine {engine}: {exc}") from exc

    width, height = render["resolution"]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = render["fps"]
    scene.render.fps_base = 1.0
    scene.render.film_transparent = render["film_transparent"]

    if engine == "CYCLES":
        scene.cycles.samples = render["samples"]
        scene.cycles.device = "CPU"
    elif engine == "BLENDER_EEVEE":
        scene.eevee.taa_render_samples = render["samples"]

    if render["view_transform"] is not None:
        try:
            scene.view_settings.view_transform = render["view_transform"]
        except TypeError as exc:
            raise TaskError(f"unknown view_transform: {render['view_transform']}") from exc
    if render["look"] is not None:
        try:
            scene.view_settings.look = render["look"]
        except TypeError as exc:
            raise TaskError(f"unknown color look: {render['look']}") from exc

    if render["format"] == "png":
        scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA" if render["film_transparent"] else "RGB"
        scene.render.image_settings.color_depth = "8"
    else:
        # Blender 5.2: video requires media_type = VIDEO before FFMPEG.
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "NONE"

    scene.render.filepath = render["output"]


def render(scene, render_spec):
    output = render_spec["output"]
    directory = os.path.dirname(output)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if render_spec["format"] == "png":
        scene.frame_set(render_spec["frame"])
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    if not os.path.isfile(output):
        raise TaskError(f"render finished but output is missing: {output}")
