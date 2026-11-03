"""Geometry Nodes asset registry and modifier application.

The registry is the stable interface between task JSON and node groups.
Socket identifiers are read from each node group's interface at apply time;
they are never hard-coded.
"""

from __future__ import annotations

import json
import os

import bpy

from .task_schema import TaskError

SOCKET_TYPES = {
    "float": "NodeSocketFloat",
    "int": "NodeSocketInt",
    "bool": "NodeSocketBool",
    "vector": "NodeSocketVector",
    "color": "NodeSocketColor",
    "string": "NodeSocketString",
    "material": "NodeSocketMaterial",
}

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_REGISTRY_RELATIVE = os.path.join("BlenderStudio", "assets", "geometry_nodes", "registry.json")
_GROUP_CACHE = {}


def registry_path(workspace=None):
    workspace = workspace or os.getcwd()
    candidate = os.path.join(workspace, _REGISTRY_RELATIVE)
    if os.path.isfile(candidate):
        return candidate
    fallback = os.path.join(_WORKSPACE, _REGISTRY_RELATIVE)
    if os.path.isfile(fallback):
        return fallback
    raise TaskError(f"geometry nodes registry not found: {candidate}")


def load_registry(workspace=None):
    path = registry_path(workspace)
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema_version") != 1:
        raise TaskError("geometry nodes registry schema_version must be 1")
    assets = data.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise TaskError("geometry nodes registry has no assets")
    return path, assets


def _asset_spec(assets, asset_id):
    spec = assets.get(asset_id)
    if spec is None:
        raise TaskError(
            f"unknown geometry nodes asset: {asset_id}; available: {sorted(assets)}"
        )
    return spec


def _validate_params(asset_id, spec, params):
    inputs = spec.get("inputs", {})
    unknown = [key for key in params if key not in inputs]
    if unknown:
        raise TaskError(f"{asset_id}: unknown inputs {sorted(unknown)}; expected {sorted(inputs)}")
    normalized = {}
    for name, definition in inputs.items():
        if name in params:
            value = params[name]
        elif "default" in definition:
            value = definition["default"]
        elif definition.get("required", True):
            raise TaskError(f"{asset_id}: missing input {name}")
        else:
            continue
        value_type = definition.get("type", "float")
        if value_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise TaskError(f"{asset_id}.{name} must be an integer")
        elif value_type == "bool":
            if not isinstance(value, bool):
                raise TaskError(f"{asset_id}.{name} must be a boolean")
        elif value_type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TaskError(f"{asset_id}.{name} must be a number")
            value = float(value)
        elif value_type == "vector":
            if not isinstance(value, (list, tuple)) or len(value) != 3:
                raise TaskError(f"{asset_id}.{name} must be [x, y, z]")
            value = tuple(float(item) for item in value)
        elif value_type in {"string", "material"}:
            if not isinstance(value, str) or not value:
                raise TaskError(f"{asset_id}.{name} must be a non-empty string")
        else:
            raise TaskError(f"{asset_id}.{name} has unsupported type {value_type}")
        minimum = definition.get("min")
        maximum = definition.get("max")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if minimum is not None and value < minimum:
                raise TaskError(f"{asset_id}.{name} must be >= {minimum}")
            if maximum is not None and value > maximum:
                raise TaskError(f"{asset_id}.{name} must be <= {maximum}")
        normalized[name] = value
    return normalized


def _resolve_material(asset_id, name, value, materials):
    if materials is None:
        raise TaskError(f"{asset_id}.{name} requires a material but none were defined")
    material = materials.get(value)
    if material is None:
        raise TaskError(
            f"{asset_id}.{name} references unknown material: {value}; "
            f"available: {sorted(materials)}"
        )
    return material


def load_group(blend_path, node_group_name):
    absolute = os.path.abspath(blend_path)
    if not os.path.isfile(absolute):
        raise TaskError(f"geometry nodes library not found: {absolute}")
    key = (absolute, node_group_name)
    if key in _GROUP_CACHE:
        return _GROUP_CACHE[key]
    with bpy.data.libraries.load(absolute, link=False) as (data_from, data_to):
        if node_group_name not in data_from.node_groups:
            raise TaskError(
                f"node group {node_group_name} not found in {blend_path}; "
                f"available: {sorted(data_from.node_groups)}"
            )
        data_to.node_groups = [node_group_name]
    group = data_to.node_groups[0]
    if group is None:
        raise TaskError(f"failed to load node group {node_group_name}")
    _GROUP_CACHE[key] = group
    return group


def _interface_inputs(group):
    result = {}
    for item in group.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT":
            result[item.name] = item
    return result


def _check_interface(asset_id, group, spec):
    available = _interface_inputs(group)
    missing = []
    mismatched = []
    for name, definition in spec.get("inputs", {}).items():
        item = available.get(name)
        expected = SOCKET_TYPES.get(definition.get("type", "float"))
        if item is None:
            missing.append(name)
        elif expected is not None and item.socket_type != expected:
            mismatched.append(f"{name}: expected {expected}, found {item.socket_type}")
    if missing:
        raise TaskError(
            f"{asset_id}: node group interface is missing inputs {missing}; "
            f"available: {sorted(available)}"
        )
    if mismatched:
        raise TaskError(f"{asset_id}: node group interface mismatch: {mismatched}")


def apply_to_object(obj, entries, materials=None, workspace=None):
    if not entries:
        return []
    registry_file, assets = load_registry(workspace)
    workspace_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(registry_file)))
    )
    applied = []
    for index, entry in enumerate(entries):
        asset_id = entry["asset"]
        spec = _asset_spec(assets, asset_id)
        params = _validate_params(asset_id, spec, entry["params"])
        blend_path = os.path.join(workspace_root, spec["blend"])
        group = load_group(blend_path, spec["node_group"])
        _check_interface(asset_id, group, spec)

        modifier = obj.modifiers.new(name=f"GN:{asset_id}:{index}", type="NODES")
        modifier.node_group = group
        interface = _interface_inputs(group)
        for name, value in params.items():
            definition = spec.get("inputs", {}).get(name, {})
            if definition.get("type") == "material":
                value = _resolve_material(asset_id, name, value, materials)
            identifier = interface[name].identifier
            if hasattr(modifier, "properties") and hasattr(modifier.properties, "inputs"):
                # Blender 5.2+: modifier inputs are structs with a `.value` field.
                getattr(modifier.properties.inputs, identifier).value = value
            else:  # Blender 4.x ID-property fallback
                modifier[identifier] = value
        applied.append(asset_id)
    obj.update_tag()
    return applied
