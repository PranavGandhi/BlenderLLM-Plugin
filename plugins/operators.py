"""Blender operators for asking, reviewing, and applying generated code."""

from __future__ import annotations

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
    build_cad_brief,
    build_repair_prompt,
    build_runtime_repair_prompt,
    build_user_prompt,
    normalize_api_key,
    validate_cad_pipeline,
)
from .inspection import (
    capture_viewport_snapshot,
    inspect_scene_after_apply,
    inspection_json,
    inspection_report,
    validate_scene_against_prompt,
)
from .runtime import run_blender_code
from .scene import scene_context_json
from .text_blocks import current_generated_code, generated_text_block, set_generated_code


_ASK_JOB: dict[str, Any] = {"thread": None, "result": None}
_RUNTIME_REPAIR_JOB: dict[str, Any] = {"thread": None, "result": None}


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
    if getattr(prefs, "api_key_source", "ENV_FILE") == "PREFERENCE":
        return getattr(prefs, "api_key", ""), "Blender preference key"

    return local_settings_key(), "packaged .env key"


def configured_client(prefs, timeout: int = 90) -> OpenAIResponsesClient:
    api_key, _source = configured_api_key(prefs)
    return OpenAIResponsesClient(
        api_key=api_key,
        timeout=timeout,
        organization="",
        project="",
    )


def run_runtime_repair_pipeline(
    *,
    api_key: str,
    model: str,
    scene_json: str | None,
    prompt: str,
    cad_brief: list[str],
    code: str,
    runtime_failures: list[str],
    inspection_text: str,
    inspection_payload: str,
    snapshot_status: str,
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
        failures = runtime_failures
        result = None
        repair_count = 0
        attempts = max(1, repair_attempts)
        for attempt in range(attempts):
            repair_count = attempt + 1
            result = client.create_blender_response(
                model=model,
                instructions=SYSTEM_PROMPT,
                user_input=build_runtime_repair_prompt(
                    original_prompt=prompt,
                    cad_brief=cad_brief,
                    code=code if result is None else result.code,
                    runtime_failures=failures,
                    scene_json=scene_json,
                    inspection_report=inspection_text,
                    inspection_json=inspection_payload,
                    snapshot_status=snapshot_status,
                ),
            )
            failures = validate_cad_pipeline(prompt, result.code)
            if not failures:
                break
        if result is None:
            raise RuntimeError("Runtime repair did not return a result.")
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    return {
        "ok": True,
        "result": result,
        "failures": failures,
        "repair_count": repair_count,
    }


def run_ask_pipeline(
    *,
    api_key: str,
    key_source: str,
    model: str,
    scene_json: str | None,
    prompt: str,
    cad_brief: list[str],
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
            user_input=build_user_prompt(prompt, scene_json, cad_brief),
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
                    cad_brief=cad_brief,
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
        state.cad_brief = ""
        state.design_plan = ""
        state.validation_report = ""
        state.scene_inspection = ""
        state.snapshot_path = ""
        state.runtime_repair_status = ""
        state.pipeline_status = "Prompt -> background LLM job"

        raw_key, source = configured_api_key(prefs)
        api_key = normalize_api_key(raw_key)
        model = state.model.strip() or prefs.default_model.strip() or DEFAULT_MODEL
        scene_json = scene_context_json() if state.include_scene_context else None
        timeout = int(state.request_timeout)
        prompt = state.prompt
        cad_brief = build_cad_brief(prompt)
        state.cad_brief = "\n".join(f"- {item}" for item in cad_brief)
        repair_attempts = int(state.repair_attempts)
        organization = ""
        project = ""

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
                        cad_brief=cad_brief,
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
        if result.cad_brief:
            state.cad_brief = "\n".join(f"- {item}" for item in result.cad_brief)
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
    bl_description = "Run generated Blender Python, inspect the result, and request repair if needed"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None

    def _start_runtime_repair(
        self,
        context: bpy.types.Context,
        state,
        *,
        source: str,
        failures: list[str],
        inspection_text: str = "",
        inspection_payload: str = "{}",
        snapshot_status: str = "",
    ) -> set[str]:
        prefs = addon_preferences()
        raw_key, _source = configured_api_key(prefs)
        api_key = normalize_api_key(raw_key)
        if not api_key:
            state.runtime_repair_status = "Runtime repair skipped: no OpenAI API key configured."
            return {"CANCELLED"}

        if _RUNTIME_REPAIR_JOB.get("thread") is not None and _RUNTIME_REPAIR_JOB["thread"].is_alive():
            state.runtime_repair_status = "Runtime repair already running."
            self.report({"WARNING"}, state.runtime_repair_status)
            return {"CANCELLED"}

        prompt = state.prompt
        cad_brief = build_cad_brief(prompt)
        model = state.model.strip() or prefs.default_model.strip() or DEFAULT_MODEL
        scene_json = scene_context_json() if state.include_scene_context else None
        timeout = int(state.request_timeout)
        repair_attempts = int(state.repair_attempts)
        organization = ""
        project = ""

        _RUNTIME_REPAIR_JOB["result"] = None
        thread = threading.Thread(
            target=lambda: _RUNTIME_REPAIR_JOB.update(
                {
                    "result": run_runtime_repair_pipeline(
                        api_key=api_key,
                        model=model,
                        scene_json=scene_json,
                        prompt=prompt,
                        cad_brief=cad_brief,
                        code=source,
                        runtime_failures=failures,
                        inspection_text=inspection_text,
                        inspection_payload=inspection_payload,
                        snapshot_status=snapshot_status,
                        repair_attempts=repair_attempts,
                        timeout=timeout,
                        organization=organization,
                        project=project,
                    )
                }
            ),
            daemon=True,
        )
        _RUNTIME_REPAIR_JOB["thread"] = thread
        thread.start()
        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        state.runtime_repair_status = "Runtime repair request started in the background."
        state.pipeline_status = "Runtime repair running"
        self.report({"WARNING"}, "Apply found runtime issues; requesting repaired code.")
        return {"RUNNING_MODAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.scene.blenderllm_plugin
        source = current_generated_code(state).strip()
        state.last_error = ""
        state.scene_inspection = ""
        state.snapshot_path = ""
        state.runtime_repair_status = ""

        if not source:
            state.last_error = "No generated code yet. Click Ask to run the CAD pipeline, then Apply."
            state.pipeline_status = "Waiting for Ask"
            self.report({"WARNING"}, state.last_error)
            return {"CANCELLED"}

        before_names = {obj.name for obj in context.scene.objects}
        try:
            run_blender_code(source)
        except Exception:
            state.last_error = traceback.format_exc()
            failures = ["Runtime execution failed: " + state.last_error.splitlines()[-1]]
            return self._start_runtime_repair(
                context,
                state,
                source=source,
                failures=failures,
                inspection_text="Execution failed before scene inspection completed.",
                inspection_payload="{}",
                snapshot_status="Snapshot skipped because execution failed.",
            )

        inspection = inspect_scene_after_apply(before_names)
        inspection_text = inspection_report(inspection)
        inspection_payload = inspection_json(inspection)
        state.scene_inspection = inspection_text
        snapshot_path, snapshot_status = capture_viewport_snapshot(context)
        state.snapshot_path = snapshot_path or snapshot_status

        measured_failures = validate_scene_against_prompt(state.prompt, inspection)
        if measured_failures:
            validation_lines = state.validation_report.splitlines() if state.validation_report else []
            validation_lines.append("Post-apply scene inspection failures:")
            validation_lines.extend(f"- {item}" for item in measured_failures)
            state.validation_report = "\n".join(validation_lines)
            state.last_error = "\n".join(measured_failures)
            return self._start_runtime_repair(
                context,
                state,
                source=source,
                failures=measured_failures,
                inspection_text=inspection_text,
                inspection_payload=inspection_payload,
                snapshot_status=snapshot_status + (f" {snapshot_path}" if snapshot_path else ""),
            )

        state.last_summary = "Applied generated code and passed scene inspection."
        state.pipeline_status = "Final CAD applied and inspected"
        if snapshot_path:
            state.runtime_repair_status = "No runtime repair needed."
        self.report({"INFO"}, "BlenderLLM-Plugin code applied and inspected.")
        return {"FINISHED"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        state = context.scene.blenderllm_plugin
        thread = _RUNTIME_REPAIR_JOB.get("thread")
        if thread is not None and thread.is_alive():
            state.runtime_repair_status = "Waiting for runtime repair response..."
            return {"PASS_THROUGH"}

        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        payload = _RUNTIME_REPAIR_JOB.get("result")
        _RUNTIME_REPAIR_JOB["thread"] = None
        _RUNTIME_REPAIR_JOB["result"] = None

        if not payload:
            state.runtime_repair_status = "Runtime repair failed without a result."
            state.pipeline_status = "Runtime repair failed"
            self.report({"ERROR"}, state.runtime_repair_status)
            return {"CANCELLED"}

        if not payload.get("ok"):
            state.runtime_repair_status = "Runtime repair request failed."
            state.last_error = payload.get("error", "Unknown runtime repair failure.")
            state.pipeline_status = "Runtime repair failed"
            self.report({"ERROR"}, state.last_error[:900])
            return {"CANCELLED"}

        result = payload["result"]
        failures = payload.get("failures", [])
        set_generated_code(state, result.code)
        if result.cad_brief:
            state.cad_brief = "\n".join(f"- {item}" for item in result.cad_brief)
        state.design_plan = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(result.design_plan))
        repair_count = payload.get("repair_count", 0)
        lines = ["Runtime repair produced replacement code."]
        if repair_count:
            lines.append(f"Repair attempts: {repair_count}")
        if failures:
            lines.append("Remaining static validation failures:")
            lines.extend(f"- {item}" for item in failures)
            state.pipeline_status = "Runtime repair needs review"
            state.last_error = "\n".join(failures)
            self.report({"WARNING"}, "Runtime repair returned code with remaining static validation failures.")
        else:
            lines.append("Static validation: passed")
            lines.append("Click Apply again to execute and inspect the repaired code.")
            state.pipeline_status = "Runtime repair ready to apply"
            state.last_error = ""
            self.report({"INFO"}, "Runtime repair ready; click Apply again.")
        state.runtime_repair_status = "\n".join(lines)
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
        state.cad_brief = ""
        state.design_plan = ""
        state.validation_report = ""
        state.scene_inspection = ""
        state.snapshot_path = ""
        state.runtime_repair_status = ""
        state.pipeline_status = "Idle"
        state.last_summary = ""
        state.last_error = ""
        return {"FINISHED"}
