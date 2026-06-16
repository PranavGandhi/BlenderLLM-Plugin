"""3D View sidebar UI."""

from __future__ import annotations

import bpy
from bpy.types import Panel

from .config import GENERATED_TEXT_NAME
from .text_blocks import current_generated_code


class BLENDERLLM_PLUGIN_PT_panel(Panel):
    bl_label = "BlenderLLM-Plugin"
    bl_idname = "BLENDERLLM_PLUGIN_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderLLM"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.scene.blenderllm_plugin

        layout.prop(state, "prompt", text="")

        row = layout.row(align=True)
        row.prop(state, "include_scene_context")
        row.prop(state, "auto_run")

        layout.prop(state, "model", text="Model")
        row = layout.row(align=True)
        row.prop(state, "repair_attempts", text="Repairs")
        row.prop(state, "request_timeout", text="Timeout")

        action_row = layout.row(align=True)
        action_row.operator("blenderllm_plugin.ask", icon="PLAY")
        action_row.operator("blenderllm_plugin.apply_generated", icon="CHECKMARK")
        action_row.operator("blenderllm_plugin.open_generated", icon="TEXT")
        action_row.operator("blenderllm_plugin.clear", icon="TRASH")

        layout.operator("blenderllm_plugin.capture_scene", icon="COPYDOWN")

        if state.pipeline_status:
            box = layout.box()
            box.label(text="Pipeline")
            box.label(text=state.pipeline_status[:120])

        if state.last_summary:
            box = layout.box()
            box.label(text="Summary")
            for line in state.last_summary.splitlines():
                box.label(text=line[:120])

        if state.cad_brief:
            box = layout.box()
            box.label(text="CAD Brief")
            for line in state.cad_brief.splitlines()[:8]:
                box.label(text=line[:120])

        if state.design_plan:
            box = layout.box()
            box.label(text="Design Plan")
            for line in state.design_plan.splitlines()[:8]:
                box.label(text=line[:120])

        if state.validation_report:
            box = layout.box()
            box.label(text="Validators")
            for line in state.validation_report.splitlines()[:10]:
                box.label(text=line[:120])

        if state.scene_inspection:
            box = layout.box()
            box.label(text="Scene Inspection")
            for line in state.scene_inspection.splitlines()[:10]:
                box.label(text=line[:120])

        if state.snapshot_path:
            box = layout.box()
            box.label(text="Snapshot")
            box.label(text=state.snapshot_path[:120])

        if state.runtime_repair_status:
            box = layout.box()
            box.label(text="Runtime Repair")
            for line in state.runtime_repair_status.splitlines()[:6]:
                box.label(text=line[:120])

        if state.generated_code:
            box = layout.box()
            box.label(text="Generated Python")
            line_count = len(current_generated_code(state).splitlines())
            box.label(text=f"{line_count} lines in {GENERATED_TEXT_NAME}")
            box.operator("blenderllm_plugin.open_generated", icon="TEXT")

        if state.last_error:
            box = layout.box()
            box.alert = True
            box.label(text="Error")
            for line in state.last_error.splitlines()[:8]:
                box.label(text=line[:120])
