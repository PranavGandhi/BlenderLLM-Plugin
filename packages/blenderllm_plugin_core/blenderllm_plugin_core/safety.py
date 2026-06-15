"""Lightweight checks before executing generated Blender Python."""

from __future__ import annotations

import ast


MAX_GENERATED_CODE_CHARS = 60000
MAX_LITERAL_RANGE = 5000

BLOCKED_IMPORT_ROOTS = {
    "http",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "urllib",
}
BLOCKED_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
}
BLOCKED_ATTR_CALLS = {
    ("os", "remove"),
    ("os", "rmdir"),
    ("os", "system"),
    ("os", "unlink"),
    ("shutil", "rmtree"),
    ("subprocess", "Popen"),
    ("subprocess", "run"),
}


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


def validate_generated_code(source: str) -> list[str]:
    """Return warnings for obviously risky code.

    This is not a sandbox. It catches common hazards while keeping normal Blender
    scripting flexible enough for generated modeling code.
    """

    warnings: list[str] = []
    if len(source) > MAX_GENERATED_CODE_CHARS:
        warnings.append(f"Generated code is too large: {len(source)} chars > {MAX_GENERATED_CODE_CHARS}.")
    if ".use_auto_smooth" in source:
        warnings.append("Generated code uses obsolete mesh.use_auto_smooth; it will be removed before Apply.")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"Syntax error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BLOCKED_IMPORT_ROOTS:
                    warnings.append(f"Blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in BLOCKED_IMPORT_ROOTS:
                warnings.append(f"Blocked import: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                warnings.append(f"Blocked call: {node.func.id}()")
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                pair = (node.func.value.id, node.func.attr)
                if pair in BLOCKED_ATTR_CALLS:
                    warnings.append(f"Blocked call: {pair[0]}.{pair[1]}()")
            call_name = _call_name(node.func)
            if call_name == "range" and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, int):
                    if first_arg.value > MAX_LITERAL_RANGE:
                        warnings.append(f"Blocked large range(): {first_arg.value} > {MAX_LITERAL_RANGE}.")
            if call_name.endswith("primitive_grid_add"):
                warnings.append("Blocked grid primitive generation; it can create excessive geometry.")
        elif isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                warnings.append("Blocked infinite while True loop.")

    return sorted(set(warnings))
