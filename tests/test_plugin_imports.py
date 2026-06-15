from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = PROJECT_ROOT / "plugins" / "blenderllm_plugin"
CORE_PATH = PROJECT_ROOT / "packages" / "blenderllm_plugin_core"
ZIP_PATH = PROJECT_ROOT / "dist" / "blenderllm_plugin-0.9.0.zip"


def install_bpy_stub() -> None:
    bpy = types.ModuleType("bpy")
    bpy.context = MagicMock()
    bpy.context.preferences.addons = {"blenderllm_plugin": MagicMock()}
    bpy.context.scene = MagicMock()
    bpy.context.selected_objects = []
    bpy.data = MagicMock()
    bpy.ops = MagicMock()
    bpy.props = types.SimpleNamespace(
        BoolProperty=lambda **_kwargs: None,
        IntProperty=lambda **_kwargs: None,
        PointerProperty=lambda **_kwargs: None,
        StringProperty=lambda **_kwargs: None,
    )
    bpy.types = types.SimpleNamespace(
        AddonPreferences=object,
        Context=object,
        Object=object,
        Operator=object,
        Panel=object,
        PropertyGroup=object,
        Scene=type("Scene", (), {}),
        Text=object,
    )
    bpy.utils = types.SimpleNamespace(
        register_class=MagicMock(),
        unregister_class=MagicMock(),
    )
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy.props
    sys.modules["bpy.types"] = bpy.types


class PluginImportTests(unittest.TestCase):
    def setUp(self) -> None:
        install_bpy_stub()
        sys.path.insert(0, str(PLUGIN_PATH))
        sys.path.insert(0, str(CORE_PATH))
        for name in list(sys.modules):
            if name == "blenderllm_plugin" or name.startswith("blenderllm_plugin."):
                del sys.modules[name]

    def tearDown(self) -> None:
        for path in (str(PLUGIN_PATH), str(CORE_PATH)):
            if path in sys.path:
                sys.path.remove(path)

    def test_plugin_registers_with_bpy_stub(self) -> None:
        plugin = importlib.import_module("blenderllm_plugin")
        plugin.register()
        plugin.unregister()

    def test_runtime_rewrites_blender_42_cone_keywords(self) -> None:
        runtime = importlib.import_module("blenderllm_plugin.runtime")
        source = "bpy.ops.mesh.primitive_cone_add(diameter1=70, diameter2=20, depth=30)\n"
        normalized = runtime.normalize_blender_api_code(source)
        self.assertIn("radius1=70 / 2.0", normalized)
        self.assertIn("radius2=20 / 2.0", normalized)
        self.assertNotIn("diameter1", normalized)
        self.assertNotIn("diameter2", normalized)

    def test_packaged_zip_registers_with_bpy_stub(self) -> None:
        if not ZIP_PATH.exists():
            self.skipTest("Build dist/blenderllm_plugin-0.9.0.zip before running packaged import test.")

        for path in (str(PLUGIN_PATH), str(CORE_PATH)):
            if path in sys.path:
                sys.path.remove(path)
        sys.path.insert(0, str(ZIP_PATH))
        for name in list(sys.modules):
            if name == "blenderllm_plugin" or name.startswith("blenderllm_plugin."):
                del sys.modules[name]

        plugin = importlib.import_module("blenderllm_plugin")
        plugin.register()
        plugin.unregister()
        sys.path.remove(str(ZIP_PATH))


if __name__ == "__main__":
    unittest.main()
