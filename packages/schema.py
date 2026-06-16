"""Structured output schema for OpenAI Responses."""

from __future__ import annotations


RESPONSE_TEXT_FORMAT = {
    "type": "json_schema",
    "name": "blenderllm_plugin_response",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "cad_brief": {"type": "array", "items": {"type": "string"}},
            "design_plan": {"type": "array", "items": {"type": "string"}},
            "code": {"type": "string"},
            "validation_targets": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "cad_brief", "design_plan", "code", "validation_targets", "warnings"],
    },
}
