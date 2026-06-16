"""Prompt templates for Blender code generation."""

from __future__ import annotations


SYSTEM_PROMPT = """You are BlenderLLM-Plugin, an expert Blender Python assistant running inside Blender.

Workflow:
1. Classify the request: new part, assembly, scene edit, modification, inspection-only, or question-only.
2. Write a CAD brief before planning: model, units, coordinate convention, specified dimensions, required features, assumptions, and validation targets.
3. Create a design plan from the brief using named parameters and stable object names.
4. Generate CAD-like Blender geometry code.
5. Include validation targets that a geometry/constraint validator can check.
6. If repairing, classify each failure and change the smallest responsible source section.

Return only JSON with these fields:
- summary: short human-readable description of what you will do.
- cad_brief: ordered list of concise brief notes: task type, units, dimensions, features, assumptions, validation targets.
- design_plan: ordered list of concrete design steps and assumptions.
- code: complete Python code that can be executed inside Blender with bpy imported.
- validation_targets: ordered list of dimensions, features, and constraints the code is intended to satisfy.
- warnings: list of short cautions, or an empty list.

Rules:
- Generate deterministic, directly executable Blender Python.
- Target Blender 4.2 Python APIs only.
- Use bpy.data and explicit object names where practical.
- Prefer editing the current scene over deleting everything unless the user asks for a reset.
- Do not use network access, file deletion, subprocesses, hidden modal UI, or add-on installation code.
- If the user asks a question that does not require scene edits, set code to an empty string.
- Keep geometry reasonably clean: named objects, applied materials, sensible origins, and real mesh solids.
- Use millimeters as the modeling unit when the prompt describes physical CAD.
- Set scene.unit_settings.system = 'METRIC' and scene.unit_settings.scale_length = 0.001 for physical CAD prompts.
- Put every prompt dimension and inferred default in named constants near the top of the code.
- Use explicit object names and custom properties for validation-friendly metadata when practical.
- Prefer mesh construction or deterministic primitive operations over fragile topology/index selections.
- For screw caps, model the cap body, inner diameter, grip/knurl detail, and a simple helical/thread-like internal ridge when practical.
- Do not use mesh.use_auto_smooth; it is obsolete in current Blender versions.
- For bpy.ops.mesh.primitive_cone_add use radius1, radius2, depth; never diameter1 or diameter2.
- For bpy.ops.mesh.primitive_cylinder_add use radius and depth; never diameter.
"""


def build_user_prompt(prompt: str, scene_json: str | None, cad_brief: list[str] | None = None) -> str:
    user_content = prompt.strip()
    if cad_brief:
        user_content += "\n\nCAD brief generated from prompt:\n" + "\n".join(f"- {item}" for item in cad_brief)
    if scene_json:
        user_content += "\n\nCurrent Blender scene JSON:\n" + scene_json
    return user_content


def build_repair_prompt(
    *,
    original_prompt: str,
    cad_brief: list[str] | None,
    scene_json: str | None,
    design_plan: list[str],
    code: str,
    validation_failures: list[str],
) -> str:
    content = [
        "Repair this Blender CAD generation.",
        "",
        "Original prompt:",
        original_prompt.strip(),
        "",
        "CAD brief:",
        "\n".join(f"- {item}" for item in (cad_brief or [])) or "- none",
        "",
        "Current design plan:",
        "\n".join(f"- {item}" for item in design_plan) or "- none",
        "",
        "Current code:",
        "```python",
        code,
        "```",
        "",
        "Validation failures:",
        "\n".join(f"- {item}" for item in validation_failures),
        "",
        "Repair procedure:",
        "- Classify each failure as syntax/API, missing geometry, wrong scale, missing feature, unsafe code, or constraint mismatch.",
        "- Change the smallest responsible part of the generated code and brief.",
        "- Preserve all prompt dimensions and already-correct features.",
        "",
        "Return a corrected full JSON response using the required schema.",
    ]
    if scene_json:
        content.extend(["", "Current Blender scene JSON:", scene_json])
    return "\n".join(content)


def build_runtime_repair_prompt(
    *,
    original_prompt: str,
    cad_brief: list[str] | None,
    code: str,
    runtime_failures: list[str],
    scene_json: str | None,
    inspection_report: str,
    inspection_json: str,
    snapshot_status: str,
) -> str:
    content = [
        "Repair this Blender CAD generation after runtime execution or post-apply validation.",
        "",
        "Original prompt:",
        original_prompt.strip(),
        "",
        "CAD brief:",
        "\n".join(f"- {item}" for item in (cad_brief or [])) or "- none",
        "",
        "Runtime or measured validation failures:",
        "\n".join(f"- {item}" for item in runtime_failures) or "- none",
        "",
        "Measured scene inspection:",
        inspection_report or "No scene inspection available.",
        "",
        "Scene inspection JSON:",
        inspection_json or "{}",
        "",
        "Snapshot status:",
        snapshot_status or "No snapshot attempted.",
        "",
        "Current code:",
        "```python",
        code,
        "```",
        "",
        "Repair procedure:",
        "- Treat measured dimensions and execution tracebacks as stronger evidence than the original plan.",
        "- Keep working features and prompt dimensions intact.",
        "- Fix Blender API errors, missing objects, wrong units, wrong dimensions, missing named features, or fragile operations.",
        "- Return complete replacement code, not a patch.",
        "",
        "Return a corrected full JSON response using the required schema.",
    ]
    if scene_json:
        content.extend(["", "Current Blender scene JSON:", scene_json])
    return "\n".join(content)
