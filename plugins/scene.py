"""Scene serialization for assistant context."""

from __future__ import annotations

import json
from typing import Any

import bpy


def vector_to_list(values: Any) -> list[float]:
    return [round(float(value), 6) for value in values]


def object_to_dict(obj: bpy.types.Object) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": obj.name,
        "type": obj.type,
        "location": vector_to_list(obj.location),
        "rotation_euler": vector_to_list(obj.rotation_euler),
        "scale": vector_to_list(obj.scale),
        "dimensions": vector_to_list(obj.dimensions),
        "visible": bool(obj.visible_get()),
    }

    if obj.type == "MESH" and obj.data is not None:
        item["vertex_count"] = len(obj.data.vertices)
        item["face_count"] = len(obj.data.polygons)
        material_names = [slot.material.name for slot in obj.material_slots if slot.material]
        if material_names:
            item["materials"] = material_names
    return item


def scene_context_json(max_objects: int = 80) -> str:
    scene = bpy.context.scene
    objects = sorted(scene.objects, key=lambda item: item.name)
    selected = [obj.name for obj in bpy.context.selected_objects]
    payload = {
        "scene": scene.name,
        "frame": int(scene.frame_current),
        "unit_system": scene.unit_settings.system,
        "object_count": len(objects),
        "selected_objects": selected,
        "objects": [object_to_dict(obj) for obj in objects[:max_objects]],
    }
    if len(objects) > max_objects:
        payload["truncated_objects"] = len(objects) - max_objects
    return json.dumps(payload, indent=2, sort_keys=True)
