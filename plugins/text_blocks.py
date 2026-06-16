"""Generated code text-block helpers."""

from __future__ import annotations

import bpy

from .config import GENERATED_TEXT_NAME


def generated_text_block() -> bpy.types.Text:
    text = bpy.data.texts.get(GENERATED_TEXT_NAME)
    if text is None:
        text = bpy.data.texts.new(GENERATED_TEXT_NAME)
    return text


def set_generated_code(state, source: str) -> None:
    state.generated_code = source
    text = generated_text_block()
    text.clear()
    text.write(source)


def current_generated_code(state) -> str:
    text = bpy.data.texts.get(GENERATED_TEXT_NAME)
    if text is not None:
        return text.as_string()
    return state.generated_code
