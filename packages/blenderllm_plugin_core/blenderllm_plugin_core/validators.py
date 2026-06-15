"""Local geometry and constraint validators for generated Blender CAD code."""

from __future__ import annotations

import ast
import re

from .safety import validate_generated_code


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

    if "screw" in prompt_lower and "thread" not in code.lower():
        failures.append("Constraint validator: screw/cap prompt should include an explicit thread or thread-like feature.")
    if "cap" in prompt_lower and "cap" not in code.lower():
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
