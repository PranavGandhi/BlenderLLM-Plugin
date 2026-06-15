"""Response parsing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AssistantResult:
    summary: str
    design_plan: list[str]
    code: str
    validation_targets: list[str]
    warnings: list[str]


def strip_code_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def parse_assistant_result(text: str) -> AssistantResult:
    cleaned = strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        code_match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        code = code_match.group(1).strip() if code_match else ""
        summary = text.strip() if not code else "The model returned Python code."
        return AssistantResult(
            summary=summary,
            design_plan=[],
            code=code,
            validation_targets=[],
            warnings=["The response was not valid JSON."],
        )

    warnings = data.get("warnings", [])
    if isinstance(warnings, str):
        warnings = [warnings]
    if not isinstance(warnings, list):
        warnings = []
    design_plan = data.get("design_plan", [])
    if isinstance(design_plan, str):
        design_plan = [design_plan]
    if not isinstance(design_plan, list):
        design_plan = []
    validation_targets = data.get("validation_targets", [])
    if isinstance(validation_targets, str):
        validation_targets = [validation_targets]
    if not isinstance(validation_targets, list):
        validation_targets = []

    return AssistantResult(
        summary=str(data.get("summary", "")).strip(),
        design_plan=[str(item).strip() for item in design_plan if str(item).strip()],
        code=str(data.get("code", "")).strip(),
        validation_targets=[str(item).strip() for item in validation_targets if str(item).strip()],
        warnings=[str(item).strip() for item in warnings if str(item).strip()],
    )


def response_text(payload: dict[str, Any]) -> str:
    if "output_text" in payload and isinstance(payload["output_text"], str):
        return payload["output_text"]

    chunks: list[str] = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and "text" in content:
                chunks.append(str(content["text"]))
    return "\n".join(chunks).strip()
