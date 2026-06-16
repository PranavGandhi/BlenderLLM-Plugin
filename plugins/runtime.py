"""Execution helpers for generated Blender Python."""

from __future__ import annotations

import ast

import bpy

from .core_imports import validate_generated_code


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = [node.attr]
        value = node.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def _half_expr(node: ast.expr) -> ast.expr:
    return ast.BinOp(left=node, op=ast.Div(), right=ast.Constant(value=2.0))


class BlenderApiCompatibilityTransformer(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        call_name = _call_name(node.func)

        if call_name.endswith("primitive_cone_add"):
            for keyword in node.keywords:
                if keyword.arg == "diameter1":
                    keyword.arg = "radius1"
                    keyword.value = _half_expr(keyword.value)
                elif keyword.arg == "diameter2":
                    keyword.arg = "radius2"
                    keyword.value = _half_expr(keyword.value)

        if call_name.endswith("primitive_cylinder_add"):
            for keyword in node.keywords:
                if keyword.arg == "diameter":
                    keyword.arg = "radius"
                    keyword.value = _half_expr(keyword.value)

        return node


def normalize_blender_api_code(source: str) -> str:
    """Remove or rewrite generated code that targets old Blender APIs."""

    normalized_lines: list[str] = []
    for line in source.splitlines():
        if ".use_auto_smooth" in line:
            continue
        normalized_lines.append(line)
    normalized_source = "\n".join(normalized_lines)

    try:
        tree = ast.parse(normalized_source)
    except SyntaxError:
        return normalized_source

    tree = BlenderApiCompatibilityTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree)
    except Exception:
        return normalized_source


def run_blender_code(source: str) -> None:
    source = normalize_blender_api_code(source)
    warnings = validate_generated_code(source)
    if warnings:
        raise RuntimeError("Generated code failed safety checks: " + "; ".join(warnings))

    namespace = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
        "bpy": bpy,
    }
    compile(source, "<blender-codex>", "exec")
    bpy.ops.ed.undo_push(message="Before BlenderLLM-Plugin")
    exec(source, namespace)
