"""Local geometry and constraint validators for generated Blender CAD code."""

from __future__ import annotations

import ast
import re

from .safety import validate_generated_code

CAD_FEATURE_KEYWORDS = {
    "hole": ("hole", "bore", "cut", "subtract", "boolean", "difference"),
    "holes": ("hole", "bore", "cut", "subtract", "boolean", "difference"),
    "cutout": ("cutout", "cut", "subtract", "boolean", "difference"),
    "slot": ("slot", "cut", "subtract", "boolean", "difference"),
    "boss": ("boss", "standoff", "cylinder"),
    "bosses": ("boss", "standoff", "cylinder"),
    "standoff": ("standoff", "boss", "cylinder"),
    "rib": ("rib", "gusset"),
    "ribs": ("rib", "gusset"),
    "gusset": ("gusset", "rib"),
    "fillet": ("fillet", "bevel"),
    "fillets": ("fillet", "bevel"),
    "chamfer": ("chamfer", "bevel"),
    "bevel": ("bevel", "chamfer", "fillet"),
    "shell": ("shell", "hollow", "solidify", "wall"),
    "hollow": ("hollow", "shell", "solidify", "wall"),
    "knurl": ("knurl", "grip", "rib", "tooth"),
    "knurled": ("knurl", "grip", "rib", "tooth"),
    "thread": ("thread", "helix", "ridge"),
    "threads": ("thread", "helix", "ridge"),
}

PHYSICAL_CAD_HINTS = (
    "mm", "cm", "m3", "m4", "m5", "m6", "m8", "m10", "m12",
    "diameter", "radius", "hole", "bore", "cap", "bracket", "enclosure",
    "plate", "flange", "thread", "screw", "boss", "standoff", "wall",
)


def prompt_mentions_physical_cad(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(hint in lowered for hint in PHYSICAL_CAD_HINTS)


def build_cad_brief(prompt: str) -> list[str]:
    lowered = prompt.lower()
    brief = ["Task type: generate Blender CAD geometry."]
    if prompt_mentions_physical_cad(prompt):
        brief.append("Units: millimeters; scene should use metric scale_length 0.001.")
    dimensions: list[str] = []
    dimensions.extend(f"M{match.group(1)} nominal interface" for match in re.finditer(r"\bm\s*(\d+(?:\.\d+)?)\b", lowered))
    dimensions.extend(f"{match.group(1)} cm = {float(match.group(1)) * 10:g} mm" for match in re.finditer(r"(\d+(?:\.\d+)?)\s*cm\b", lowered))
    dimensions.extend(f"{match.group(1)} mm" for match in re.finditer(r"(\d+(?:\.\d+)?)\s*mm\b", lowered))
    if dimensions:
        brief.append("Specified dimensions: " + "; ".join(dict.fromkeys(dimensions)))
    features = [word for word in CAD_FEATURE_KEYWORDS if re.search(rf"\b{re.escape(word)}\b", lowered)]
    if features:
        brief.append("Required features: " + ", ".join(dict.fromkeys(features)))
    brief.append("Validation targets: syntax-safe bpy code, creates mesh solids, preserves specified dimensions and required features.")
    return brief


def _number_tokens(source: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", source))


def _has_number(source: str, value: float) -> bool:
    tokens = _number_tokens(source)
    candidates = {
        str(int(value)) if value.is_integer() else str(value),
        str(round(value, 3)).rstrip("0").rstrip("."),
    }
    return any(candidate in tokens for candidate in candidates)


def _constraint_failures(prompt: str, code: str) -> list[str]:
    failures: list[str] = []
    prompt_lower = prompt.lower()

    for match in re.finditer(r"\bm\s*(\d+(?:\.\d+)?)\b", prompt_lower):
        diameter = float(match.group(1))
        radius = diameter / 2.0
        if not (_has_number(code, diameter) or _has_number(code, radius)):
            failures.append(f"Constraint validator: prompt mentions M{diameter:g}; code should contain diameter {diameter:g} mm or radius {radius:g} mm.")

    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*cm\b", prompt_lower):
        mm = float(match.group(1)) * 10.0
        if not _has_number(code, mm):
            failures.append(f"Constraint validator: prompt mentions {match.group(1)} cm; code should contain {mm:g} mm.")

    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*mm\b", prompt_lower):
        mm = float(match.group(1))
        if not _has_number(code, mm):
            failures.append(f"Constraint validator: prompt mentions {mm:g} mm; code should contain that dimension.")

    code_lower = code.lower()
    if prompt_mentions_physical_cad(prompt) and not ("unit_settings.system" in code and "METRIC" in code):
        failures.append("Constraint validator: physical CAD prompts should set Blender units to metric.")

    for feature, acceptable_terms in CAD_FEATURE_KEYWORDS.items():
        if re.search(rf"\b{re.escape(feature)}\b", prompt_lower) and not any(term in code_lower for term in acceptable_terms):
            failures.append(f"Constraint validator: prompt mentions {feature}; code should include an explicit {feature}-related feature.")

    if "screw" in prompt_lower and not any(term in code_lower for term in ("thread", "helix", "ridge")):
        failures.append("Constraint validator: screw/cap prompt should include an explicit thread or thread-like feature.")
    if "cap" in prompt_lower and "cap" not in code_lower:
        failures.append("Constraint validator: cap prompt should name at least one cap object or parameter.")

    return failures


def _geometry_failures(code: str) -> list[str]:
    failures: list[str] = []
    if not code.strip():
        return ["Geometry validator: no CAD code was generated."]

    try:
        ast.parse(code)
    except SyntaxError as exc:
        return [f"Geometry validator: generated code has a syntax error: {exc}"]

    lowered = code.lower()
    geometry_signals = [
        "bpy.ops.mesh.primitive",
        "bpy.data.meshes",
        "mesh.from_pydata",
        "bmesh",
    ]
    if not any(signal in lowered for signal in geometry_signals):
        failures.append("Geometry validator: code does not appear to create mesh geometry.")
    if "bpy" not in lowered:
        failures.append("Geometry validator: code should use Blender's bpy API.")

    return failures


def validate_cad_pipeline(prompt: str, code: str) -> list[str]:
    """Run static geometry, safety, and prompt-constraint gates."""

    failures: list[str] = []
    failures.extend(validate_generated_code(code))
    failures.extend(_geometry_failures(code))
    failures.extend(_constraint_failures(prompt, code))
    return sorted(set(failures))
