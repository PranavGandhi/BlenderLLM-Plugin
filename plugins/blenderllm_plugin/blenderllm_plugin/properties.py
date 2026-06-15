"""Scene-level add-on state."""

from __future__ import annotations

from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from .config import DEFAULT_MODEL


class BlenderLLMPluginState(PropertyGroup):
    prompt: StringProperty(
        name="Prompt",
        description="Describe what you want BlenderLLM-Plugin to create or change",
        default="Create a clean studio setup with a bevelled cube, warm key light, and camera.",
        options={"TEXTEDIT_UPDATE"},
    )
    generated_code: StringProperty(name="Generated Code", default="", options={"TEXTEDIT_UPDATE"})
    design_plan: StringProperty(name="Design Plan", default="", options={"TEXTEDIT_UPDATE"})
    validation_report: StringProperty(name="Validation Report", default="", options={"TEXTEDIT_UPDATE"})
    pipeline_status: StringProperty(name="Pipeline Status", default="Idle", options={"TEXTEDIT_UPDATE"})
    last_summary: StringProperty(name="Summary", default="", options={"TEXTEDIT_UPDATE"})
    last_error: StringProperty(name="Error", default="", options={"TEXTEDIT_UPDATE"})
    include_scene_context: BoolProperty(
        name="Scene Context",
        description="Send current object names, transforms, dimensions, mesh counts, and selection",
        default=True,
    )
    auto_run: BoolProperty(
        name="Auto Apply",
        description="Run generated Blender Python immediately after the model responds",
        default=False,
    )
    repair_attempts: IntProperty(
        name="Repairs",
        description="Maximum repair-loop attempts when validators fail",
        min=0,
        max=5,
        default=2,
    )
    request_timeout: IntProperty(
        name="Timeout",
        description="Seconds to wait for each OpenAI request",
        min=15,
        max=600,
        default=180,
    )
    model: StringProperty(name="Model", default=DEFAULT_MODEL)
