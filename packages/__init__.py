"""Shared logic for the BlenderLLM-Plugin add-on."""

from .client import OpenAIResponsesClient, api_key_fingerprint, normalize_api_key
from .models import AssistantResult, parse_assistant_result, response_text
from .prompts import SYSTEM_PROMPT, build_repair_prompt, build_runtime_repair_prompt, build_user_prompt
from .safety import validate_generated_code
from .validators import build_cad_brief, validate_cad_pipeline

__all__ = [
    "AssistantResult",
    "OpenAIResponsesClient",
    "SYSTEM_PROMPT",
    "api_key_fingerprint",
    "build_repair_prompt",
    "build_runtime_repair_prompt",
    "build_cad_brief",
    "build_user_prompt",
    "parse_assistant_result",
    "response_text",
    "normalize_api_key",
    "validate_cad_pipeline",
    "validate_generated_code",
]
