"""BlenderLLM-Plugin add-on entry point."""

from __future__ import annotations


bl_info = {
    "name": "BlenderLLM-Plugin",
    "author": "Pranav Gandhi + BlenderLLM",
    "version": (0, 9, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderLLM",
    "description": "Ask an OpenAI model to inspect and modify the current Blender scene.",
    "category": "3D View",
}


def register() -> None:
    from .addon import register as register_addon

    register_addon()


def unregister() -> None:
    from .addon import unregister as unregister_addon

    unregister_addon()
