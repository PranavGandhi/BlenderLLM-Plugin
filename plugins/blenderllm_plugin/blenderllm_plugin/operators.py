"""Blender operators for asking, reviewing, and applying generated code."""

from __future__ import annotations

import os
import threading
import traceback
from pathlib import Path
from typing import Any

import bpy
from bpy.types import Operator

from .config import DEFAULT_MODEL, GENERATED_TEXT_NAME
from .core_imports import (
    OpenAIResponsesClient,
    SYSTEM_PROMPT,
    build_repair_prompt,
    build_user_prompt,
    normalize_api_key,
    validate_cad_pipeline,
)
from .runtime import run_blender_code
from .scene import scene_context_json
from .text_blocks import current_generated_code, generated_text_block, set_generated_code


_ASK_JOB: dict[str, Any] = {"thread": None, "result": None}


def addon_preferences():
    return bpy.context.preferences.addons[__package__].preferences


def local_settings_key() -> str:
    settings_path = Path(__file__).with_name("local_settings.py")
    if not settings_path.is_file():
        return ""

    namespace: dict[str, str] = {}
    try:
        exec(compile(settings_path.read_text(encoding="utf-8"), str(settings_path), "exec"), {}, namespace)
    except Exception:
        return ""
    return str(namespace.get("OPENAI_API_KEY", ""))


def configured_api_key(prefs) -> tuple[str, str]:
    local_key = local_settings_key()
    if local_key:
        return local_key, "local_settings.py"
    if getattr(prefs, "use_environment_key", False):
        return os.environ.get("OPENAI_API_KEY", ""), "OPENAI_API_KEY environment variable"
    return prefs.api_key, "BlenderLLM-Plugin preferences"


def configured_client(prefs, timeout: int = 90) -> OpenAIResponsesClient:
    api_key, _source = configured_api_key(prefs)
    return OpenAIResponsesClient(
        api_key=api_key,
        timeout=timeout,
        organization=getattr(prefs, "organization", ""),
        project=getattr(prefs, "project", ""),
    )


def run_ask_pipeline(
    *,
    api_key: str,
    key_source: str,
    model: str,
    scene_json: str | None,
    prompt: str,
    repair_attempts: int,
    timeout: int,
    organization: str,
    project: str,
) -> dict[str, Any]:
    client = OpenAIResponsesClient(
        api_key=api_key,
        timeout=timeout,
        organization=organization,
        project=project,
    )
    try:
        result = client.create_blender_response(
            model=model,
            instructions=SYSTEM_PROMPT,
            user_input=build_user_prompt(prompt, scene_json),
        )
        failures = validate_cad_pipeline(prompt, result.code)

        repair_count = 0
        for attempt in range(repair_attempts):
            if not failures:
                break
            repair_count = attempt + 1
            result = client.create_blender_response(
                model=model,
                instructions=SYSTEM_PROMPT,
                user_input=build_repair_prompt(
                    original_prompt=prompt,
                    scene_json=scene_json,
                    design_plan=result.design_plan,
                    code=result.code,
                    validation_failures=failures,
                ),
            )
            failures = validate_cad_pipeline(prompt, result.code)
    except Exception as exc:
        message = str(exc)
        return {
            "ok": False,
            "error": message,
            "traceback": traceback.format_exc(),
        }

    return {
        "ok": True,
        "result": result,
        "failures": failures,
        "repair_count": repair_count,
    }


class BLENDERLLM_PLUGIN_OT_ask(Operator):
    bl_idname = "blenderllm_plugin.ask"
    bl_label = "Ask"
    bl_description = "Ask OpenAI to generate Blender Python for this scene"
    bl_options = {"REGISTER"}

    _timer = None

    def execute(self, context: bpy.types.Context) -> set[str]:
        return self.invoke(context, None)

    def invoke(self, context: bpy.types.Context, event) -> set[str]:
        if _ASK_JOB.get("thread") is not None and _ASK_JOB["thread"].is_alive():
            self.report({"WARNING"}, "BlenderLLM-Plugin is already asking. Wait for the current request to finish.")
            return {"CANCELLED"}

        state = context.scene.blenderllm_plugin
        prefs = addon_preferences()
        state.last_error = ""
        state.last_summary = "Working..."
        state.design_plan = ""
        state.validation_report = ""
        state.pipeline_status = "Prompt -> background LLM job"

        raw_key, source = configured_api_key(prefs)
        api_key = normalize_api_key(raw_key)
        model = state.model.strip() or prefs.default_model.strip() or DEFAULT_MODEL
        scene_json = scene_context_json() if state.include_scene_context else None
        timeout = int(state.request_timeout)
        prompt = state.prompt
        repair_attempts = int(state.repair_attempts)
        organization = getattr(prefs, "organization", "")
        project = getattr(prefs, "project", "")

        _ASK_JOB["result"] = None
        thread = threading.Thread(
            target=lambda: _ASK_JOB.update(
                {
                    "result": run_ask_pipeline(
                        api_key=api_key,
                        key_source=source,
                        model=model,
                        scene_json=scene_json,
                        prompt=prompt,
                        repair_attempts=repair_attempts,
                        timeout=timeout,
                        organization=organization,
                        project=project,
                    )
                }
            ),
            daemon=True,
        )
        _ASK_JOB["thread"] = thread
        thread.start()

        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "BlenderLLM-Plugin request started in the background.")
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        state = context.scene.blenderllm_plugin
        thread = _ASK_JOB.get("thread")
        if thread is not None and thread.is_alive():
            state.pipeline_status = "Waiting for OpenAI response..."
            return {"PASS_THROUGH"}

        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        payload = _ASK_JOB.get("result")
        _ASK_JOB["thread"] = None
        _ASK_JOB["result"] = None

        if not payload:
            state.last_summary = "Request failed."
            state.last_error = "Background request finished without a result."
            state.pipeline_status = "Failed"
            self.report({"ERROR"}, state.last_error)
            return {"CANCELLED"}

        if not payload.get("ok"):
            state.last_summary = "Request failed."
            state.last_error = payload.get("error", "Unknown OpenAI request failure.")
            state.pipeline_status = "Failed"
            self.report({"ERROR"}, state.last_error[:900])
            return {"CANCELLED"}

        result = payload["result"]
        failures = payload["failures"]

        state.last_summary = result.summary or "Response received."
        state.design_plan = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(result.design_plan))
        validation_lines = []
        if result.validation_targets:
            validation_lines.append("Targets:")
            validation_lines.extend(f"- {item}" for item in result.validation_targets)
        if failures:
            validation_lines.append("Failures:")
            validation_lines.extend(f"- {item}" for item in failures)
            state.pipeline_status = "Validation failed"
        else:
            validation_lines.append("Geometry validator: passed")
            validation_lines.append("Constraint validator: passed")
            state.pipeline_status = "Final CAD ready"
        repair_count = payload.get("repair_count", 0)
        if repair_count:
            validation_lines.append(f"Repair loop attempts: {repair_count}")
        state.validation_report = "\n".join(validation_lines)
        if result.warnings:
            state.last_summary += "\nWarnings: " + "; ".join(result.warnings)
        set_generated_code(state, result.code)

        if failures:
            state.last_error = "Validation failed. Open the generated code or adjust the prompt, then click Ask again."
            self.report({"WARNING"}, "Validation failed; code was generated but not auto-applied.")
            return {"CANCELLED"}

        if state.auto_run and state.generated_code.strip():
            return bpy.ops.blenderllm_plugin.apply_generated()

        self.report({"INFO"}, "BlenderLLM-Plugin response ready.")
        return {"FINISHED"}


class BLENDERLLM_PLUGIN_OT_apply_generated(Operator):
    bl_idname = "blenderllm_plugin.apply_generated"
    bl_label = "Apply"
    bl_description = "Run the generated Blender Python in the current scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.scene.blenderllm_plugin
        source = current_generated_code(state).strip()
        state.last_error = ""

        if not source:
            state.last_error = "No generated code yet. Click Ask to run the CAD pipeline, then Apply."
            state.pipeline_status = "Waiting for Ask"
            self.report({"WARNING"}, state.last_error)
            return {"CANCELLED"}

        try:
            run_blender_code(source)
        except Exception as exc:
            state.last_error = traceback.format_exc()
            self.report({"ERROR"}, str(exc)[:900])
            return {"CANCELLED"}

        state.last_summary = "Applied generated code."
        state.pipeline_status = "Final CAD applied"
        self.report({"INFO"}, "BlenderLLM-Plugin code applied.")
        return {"FINISHED"}


class BLENDERLLM_PLUGIN_OT_open_generated(Operator):
    bl_idname = "blenderllm_plugin.open_generated"
    bl_label = "Open Code"
    bl_description = "Open the generated Python in a Blender Text Editor"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        text = generated_text_block()
        area = context.area
        if area is not None:
            area.ui_type = "TEXT_EDITOR"
            if context.space_data is not None and hasattr(context.space_data, "text"):
                context.space_data.text = text
        self.report({"INFO"}, f"Opened {GENERATED_TEXT_NAME}.")
        return {"FINISHED"}


class BLENDERLLM_PLUGIN_OT_capture_scene(Operator):
    bl_idname = "blenderllm_plugin.capture_scene"
    bl_label = "Capture Scene"
    bl_description = "Put a compact JSON snapshot of the current scene on the clipboard"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        context.window_manager.clipboard = scene_context_json()
        self.report({"INFO"}, "Scene JSON copied to clipboard.")
        return {"FINISHED"}


class BLENDERLLM_PLUGIN_OT_clear(Operator):
    bl_idname = "blenderllm_plugin.clear"
    bl_label = "Clear"
    bl_description = "Clear the response, generated code, and error text"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.scene.blenderllm_plugin
        set_generated_code(state, "")
        state.design_plan = ""
        state.validation_report = ""
        state.pipeline_status = "Idle"
        state.last_summary = ""
        state.last_error = ""
        return {"FINISHED"}
