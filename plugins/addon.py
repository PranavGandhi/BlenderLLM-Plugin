"""Registration for the BlenderLLM-Plugin add-on."""

from __future__ import annotations

import bpy

from .operators import (
    BLENDERLLM_PLUGIN_OT_apply_generated,
    BLENDERLLM_PLUGIN_OT_ask,
    BLENDERLLM_PLUGIN_OT_capture_scene,
    BLENDERLLM_PLUGIN_OT_clear,
    BLENDERLLM_PLUGIN_OT_open_generated,
)
from .panel import BLENDERLLM_PLUGIN_PT_panel
from .preferences import BlenderLLMPluginPreferences
from .properties import BlenderLLMPluginState


classes = (
    BlenderLLMPluginPreferences,
    BlenderLLMPluginState,
    BLENDERLLM_PLUGIN_OT_ask,
    BLENDERLLM_PLUGIN_OT_apply_generated,
    BLENDERLLM_PLUGIN_OT_open_generated,
    BLENDERLLM_PLUGIN_OT_capture_scene,
    BLENDERLLM_PLUGIN_OT_clear,
    BLENDERLLM_PLUGIN_PT_panel,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blenderllm_plugin = bpy.props.PointerProperty(type=BlenderLLMPluginState)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "blenderllm_plugin"):
        del bpy.types.Scene.blenderllm_plugin
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
