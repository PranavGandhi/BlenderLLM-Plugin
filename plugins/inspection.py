"""Post-apply scene inspection and snapshot helpers."""

from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


def _vector(values: Any) -> list[float]:
    return [round(float(value), 4) for value in values]


def _bbox_world(obj: bpy.types.Object) -> tuple[list[float], list[float], list[float]]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = [min(corner[index] for corner in corners) for index in range(3)]
    maxs = [max(corner[index] for corner in corners) for index in range(3)]
    dims = [maxs[index] - mins[index] for index in range(3)]
    return _vector(mins), _vector(maxs), _vector(dims)


def _scene_scale_to_mm() -> float:
    scene = bpy.context.scene
    scale_length = float(getattr(scene.unit_settings, "scale_length", 1.0) or 1.0)
    if scene.unit_settings.system == "METRIC" and math.isclose(scale_length, 0.001, rel_tol=0.0, abs_tol=1e-9):
        return 1000.0
    return 1.0


def inspect_scene_after_apply(before_names: set[str] | None = None, max_objects: int = 24) -> dict[str, Any]:
    before_names = before_names or set()
    scale_to_mm = _scene_scale_to_mm()
    scene = bpy.context.scene
    mesh_objects = [obj for obj in scene.objects if obj.type == "MESH" and obj.visible_get()]
    new_mesh_objects = [obj for obj in mesh_objects if obj.name not in before_names]
    target_objects = new_mesh_objects or mesh_objects

    objects: list[dict[str, Any]] = []
    for obj in sorted(target_objects, key=lambda item: item.name)[:max_objects]:
        bbox_min, bbox_max, bbox_dims = _bbox_world(obj)
        dimensions_mm = [round(value * scale_to_mm, 3) for value in bbox_dims]
        objects.append(
            {
                "name": obj.name,
                "new": obj.name not in before_names,
                "type": obj.type,
                "bbox_min": bbox_min,
                "bbox_max": bbox_max,
                "dimensions_scene_units": bbox_dims,
                "dimensions_mm": dimensions_mm,
                "vertex_count": len(obj.data.vertices) if obj.data else 0,
                "face_count": len(obj.data.polygons) if obj.data else 0,
                "material_count": len([slot for slot in obj.material_slots if slot.material]),
            }
        )

    return {
        "unit_system": scene.unit_settings.system,
        "scale_length": float(getattr(scene.unit_settings, "scale_length", 1.0) or 1.0),
        "scale_to_mm": scale_to_mm,
        "visible_mesh_count": len(mesh_objects),
        "new_visible_mesh_count": len(new_mesh_objects),
        "inspected_mesh_count": len(objects),
        "objects": objects,
    }


def inspection_report(inspection: dict[str, Any]) -> str:
    lines = [
        f"Units: {inspection.get('unit_system')} scale_length={inspection.get('scale_length')}",
        f"Visible meshes: {inspection.get('visible_mesh_count')} ({inspection.get('new_visible_mesh_count')} new)",
    ]
    for obj in inspection.get("objects", []):
        dims = " x ".join(f"{value:g}" for value in obj.get("dimensions_mm", []))
        marker = "new" if obj.get("new") else "existing"
        lines.append(
            f"- {obj.get('name')} [{marker}]: {dims} mm, "
            f"{obj.get('vertex_count')} verts, {obj.get('face_count')} faces"
        )
    return "\n".join(lines)


def _prompt_dimensions_mm(prompt: str) -> list[tuple[str, float]]:
    lowered = prompt.lower()
    dimensions: list[tuple[str, float]] = []
    for match in re.finditer(r"\bm\s*(\d+(?:\.\d+)?)\b", lowered):
        value = float(match.group(1))
        dimensions.append((f"M{value:g}", value))
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*cm\b", lowered):
        value = float(match.group(1)) * 10.0
        dimensions.append((f"{match.group(1)} cm", value))
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*mm\b", lowered):
        value = float(match.group(1))
        dimensions.append((f"{value:g} mm", value))
    return dimensions


def validate_scene_against_prompt(prompt: str, inspection: dict[str, Any], tolerance_ratio: float = 0.18) -> list[str]:
    failures: list[str] = []
    objects = inspection.get("objects", [])
    prompt_lower = prompt.lower()

    if not objects:
        failures.append("Scene inspection: no visible mesh objects were created or available for measurement.")
        return failures

    if any(token in prompt_lower for token in ("mm", "cm", "m3", "m4", "m5", "m6", "m8", "m10", "m12", "diameter", "cap", "screw")):
        if inspection.get("unit_system") != "METRIC":
            failures.append("Scene inspection: physical CAD prompt should leave the scene unit system set to METRIC.")

    all_dims = [float(value) for obj in objects for value in obj.get("dimensions_mm", [])]
    for label, expected in _prompt_dimensions_mm(prompt):
        tolerance = max(0.75, expected * tolerance_ratio)
        if not any(abs(value - expected) <= tolerance for value in all_dims):
            failures.append(
                f"Scene inspection: prompt dimension {label} ({expected:g} mm) was not found in measured object bounds."
            )

    name_blob = " ".join(str(obj.get("name", "")).lower() for obj in objects)
    if "cap" in prompt_lower and "cap" not in name_blob:
        failures.append("Scene inspection: cap prompt should create at least one object named like a cap.")
    if "thread" in prompt_lower or "screw" in prompt_lower:
        if not any(term in name_blob for term in ("thread", "ridge", "helix", "cap")):
            failures.append("Scene inspection: screw/thread prompt should create a named thread, ridge, helix, or cap object.")

    return failures


def capture_viewport_snapshot(context: bpy.types.Context, prefix: str = "blenderllm_snapshot") -> tuple[str, str]:
    output_dir = Path(tempfile.gettempdir()) / "blenderllm_plugin_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_{len(list(output_dir.glob(prefix + '_*.png'))) + 1:03d}.png"

    scene = context.scene
    previous_path = scene.render.filepath
    previous_percentage = scene.render.resolution_percentage
    scene.render.filepath = str(path)
    scene.render.resolution_percentage = 50
    try:
        bpy.ops.render.opengl(write_still=True, view_context=True)
    except Exception as exc:
        scene.render.filepath = previous_path
        scene.render.resolution_percentage = previous_percentage
        return "", f"Snapshot skipped: {exc}"
    scene.render.filepath = previous_path
    scene.render.resolution_percentage = previous_percentage
    if path.exists():
        return str(path), "Snapshot captured."
    return "", "Snapshot skipped: Blender did not write an image."


def inspection_json(inspection: dict[str, Any]) -> str:
    return json.dumps(inspection, indent=2, sort_keys=True)
