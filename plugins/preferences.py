"""Blender add-on preferences."""

from __future__ import annotations

from bpy.props import BoolProperty, StringProperty
from bpy.types import AddonPreferences

from .config import ADDON_ID, DEFAULT_MODEL


class BlenderLLMPluginPreferences(AddonPreferences):
    bl_idname = ADDON_ID

    api_key: StringProperty(
        name="OpenAI API Key",
        subtype="PASSWORD",
        description="Stored locally in Blender preferences",
        default="",
        maxlen=4096,
    )
    use_environment_key: BoolProperty(
        name="Use OPENAI_API_KEY",
        description="Use the OPENAI_API_KEY environment variable instead of the preference key",
        default=False,
    )
    default_model: StringProperty(
        name="Default Model",
        description="OpenAI model used for assistant requests",
        default=DEFAULT_MODEL,
    )
    organization: StringProperty(
        name="Organization ID",
        description="Optional OpenAI organization ID for legacy/user keys",
        default="",
    )
    project: StringProperty(
        name="Project ID",
        description="Optional OpenAI project ID when a key requires an explicit project",
        default="",
    )

    def draw(self, context) -> None:
        layout = self.layout
        layout.prop(self, "api_key")
        layout.prop(self, "use_environment_key")
        layout.prop(self, "default_model")
        layout.prop(self, "organization")
        layout.prop(self, "project")
