from __future__ import annotations

import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = PROJECT_ROOT / "plugins"
CORE_PATH = PROJECT_ROOT / "packages"
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
        EnumProperty=lambda **_kwargs: None,
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
    mathutils = types.ModuleType("mathutils")

    class Vector(tuple):
        def __new__(cls, values):
            return tuple.__new__(cls, values)

    mathutils.Vector = Vector
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy.props
    sys.modules["bpy.types"] = bpy.types
    sys.modules["mathutils"] = mathutils


def clear_package(name: str) -> None:
    for module_name in list(sys.modules):
        if module_name == name or module_name.startswith(f"{name}."):
            del sys.modules[module_name]


def load_flat_package(name: str, folder: Path):
    clear_package(name)
    spec = importlib.util.spec_from_file_location(
        name,
        folder / "__init__.py",
        submodule_search_locations=[str(folder)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name} from {folder}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PluginImportTests(unittest.TestCase):
    def setUp(self) -> None:
        install_bpy_stub()
        load_flat_package("blenderllm_plugin_core", CORE_PATH)
        clear_package("blenderllm_plugin")

    def tearDown(self) -> None:
        clear_package("blenderllm_plugin")
        clear_package("blenderllm_plugin_core")

    def test_plugin_registers_with_bpy_stub(self) -> None:
        plugin = load_flat_package("blenderllm_plugin", PLUGIN_PATH)
        plugin.register()
        plugin.unregister()

    def test_runtime_rewrites_blender_42_cone_keywords(self) -> None:
        load_flat_package("blenderllm_plugin", PLUGIN_PATH)
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

        sys.path.insert(0, str(ZIP_PATH))
        clear_package("blenderllm_plugin")
        clear_package("blenderllm_plugin_core")

        plugin = importlib.import_module("blenderllm_plugin")
        plugin.register()
        plugin.unregister()
        sys.path.remove(str(ZIP_PATH))


if __name__ == "__main__":
    unittest.main()
