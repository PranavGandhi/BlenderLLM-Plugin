"""Blender add-on preferences."""

from __future__ import annotations

from pathlib import Path

from bpy.props import EnumProperty, StringProperty
from bpy.types import AddonPreferences

from .config import ADDON_ID, DEFAULT_MODEL
from .core_imports import normalize_api_key


KEY_SOURCE_ITEMS = (
    ("ENV_FILE", "Packaged .env key", "Use the OPENAI_API_KEY bundled from the project .env when the add-on zip was built"),
    ("PREFERENCE", "Blender preference key", "Use the key stored in this Blender preferences text field"),
)


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


def key_preview(value: str) -> str:
    key = normalize_api_key(value)
    if not key:
        return "Key: none | Count: 0 chars"
    start = key[:12] if len(key) > 12 else key
    end = key[-10:] if len(key) > 10 else key
    return f"Key: {start}...{end} | Count: {len(key)} chars"


def selected_key(source: str, preference_key: str) -> tuple[str, str]:
    if source == "PREFERENCE":
        return preference_key, "Blender preference key"
    return local_settings_key(), "Packaged .env key"


class BlenderLLMPluginPreferences(AddonPreferences):
    bl_idname = ADDON_ID

    api_key_source: EnumProperty(
        name="Key Source",
        description="Choose where BlenderLLM-Plugin reads the OpenAI API key from",
        items=KEY_SOURCE_ITEMS,
        default="ENV_FILE",
    )
    api_key: StringProperty(
        name="Preference OpenAI Key",
        subtype="PASSWORD",
        description="Optional key stored in Blender preferences. Some Blender builds cap this field at 127 characters.",
        default="",
        maxlen=4096,
    )
    default_model: StringProperty(
        name="Default Model",
        description="OpenAI model used for assistant requests",
        default=DEFAULT_MODEL,
    )

    def draw(self, context) -> None:
        layout = self.layout
        layout.prop(self, "api_key_source")
        layout.prop(self, "api_key")

        note = layout.box()
        note.label(text="Use Packaged .env key for long sk-proj keys.")
        note.label(text="Blender preference text fields may cut off around 127 characters on some versions.")

        key, source_label = selected_key(self.api_key_source, self.api_key)
        status = layout.box()
        status.label(text=f"Active source: {source_label}")
        status.label(text=key_preview(key))

        layout.prop(self, "default_model")
