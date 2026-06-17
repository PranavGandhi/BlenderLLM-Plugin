"""Import the bundled core package, with a source-tree fallback for development."""

from __future__ import annotations

try:
    from .core.blenderllm_plugin_core import (  # type: ignore[import-not-found]
        OpenAIResponsesClient,
        api_key_fingerprint,
        build_cad_brief,
        SYSTEM_PROMPT,
        build_repair_prompt,
        build_runtime_repair_prompt,
        build_user_prompt,
        normalize_api_key,
        validate_cad_pipeline,
        validate_generated_code,
    )
except ModuleNotFoundError:
    from blenderllm_plugin_core import (
        OpenAIResponsesClient,
        api_key_fingerprint,
        build_cad_brief,
        SYSTEM_PROMPT,
        build_repair_prompt,
        build_runtime_repair_prompt,
        build_user_prompt,
        normalize_api_key,
        validate_cad_pipeline,
        validate_generated_code,
    )


__all__ = [
    "OpenAIResponsesClient",
    "SYSTEM_PROMPT",
    "api_key_fingerprint",
    "build_repair_prompt",
    "build_runtime_repair_prompt",
    "build_cad_brief",
    "build_user_prompt",
    "normalize_api_key",
    "validate_cad_pipeline",
    "validate_generated_code",
]
