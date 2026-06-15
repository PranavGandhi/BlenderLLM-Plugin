"""Backward-compatible wrapper for building the Blender add-on ZIP."""

from __future__ import annotations

from build_blender_plugin import main


if __name__ == "__main__":
    raise SystemExit(main())
