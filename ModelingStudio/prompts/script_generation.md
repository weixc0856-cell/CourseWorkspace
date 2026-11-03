You write a Blender 5.2 Python module that builds the given modeling plan.

Hard requirements:
- Define exactly one public entry point: `def build():`.
- The model plan is embedded below. Hard-code its values in the module. Never read `bpy.context.scene.plan_data`, a JSON file, or any other runtime plan store.
- Import only from this allowlist: bpy, bmesh, mathutils, math, random.
- Do not read or write files. Do not save .blend, export meshes, or render. The caller owns all I/O.
- Do not use os, sys, pathlib, shutil, subprocess, socket, requests, urllib, importlib, eval, exec, compile, __import__, open, or dunder attributes.
- Do not call bpy.ops.wm.*, bpy.ops.export_scene.*, bpy.ops.import_scene.*, or bpy.data.libraries.
- Create every part from the plan with its exact id as the Blender object name.
- Do not leave operator-created duplicates behind. After `bpy.ops.mesh.primitive_*_add`, rename and reuse `bpy.context.active_object`; do not create a second object that shares the same mesh while the operator object remains in the scene.
- `size` is the full extent. For a cube, `primitive_cube_add(size=1)` then set `obj.dimensions = size`. For an upright cylinder, `radius = size[0] / 2` and `depth = size[2]`. For a sphere, `radius = size[0] / 2`.
- Apply location and rotation to the final object. Convert rotation from degrees to radians.
- Create the materials from the plan and assign them to the matching parts.
- Create a camera named `Camera`. Aim it at the plan camera target with `direction = target - location` and `direction.to_track_quat('-Z', 'Y').to_euler()`. Set `scene.camera`.
- Create the plan lights and aim each at its target. Set metric units. Do not set the frame range or render resolution.
- The module must run from a factory-startup background Blender process with no UI context.
- Keep the code deterministic and under 400 lines.

Return only a Python code block containing the module. No explanation.

Model plan:
{plan}
