from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


CORE_PATH = Path(__file__).resolve().parents[1] / "packages"


def load_core_package():
    spec = importlib.util.spec_from_file_location(
        "blenderllm_plugin_core",
        CORE_PATH / "__init__.py",
        submodule_search_locations=[str(CORE_PATH)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load flattened core package")
    module = importlib.util.module_from_spec(spec)
    sys.modules["blenderllm_plugin_core"] = module
    spec.loader.exec_module(module)
    return module


core = load_core_package()
api_key_fingerprint = core.api_key_fingerprint
build_cad_brief = core.build_cad_brief
normalize_api_key = core.normalize_api_key
parse_assistant_result = core.parse_assistant_result
response_text = core.response_text
validate_cad_pipeline = core.validate_cad_pipeline
validate_generated_code = core.validate_generated_code


class CoreTests(unittest.TestCase):
    def test_parse_structured_response(self) -> None:
        result = parse_assistant_result(
            '{"summary":"ok","cad_brief":["brief"],"design_plan":["plan"],"code":"print(1)","validation_targets":["target"],"warnings":[]}'
        )
        self.assertEqual(result.summary, "ok")
        self.assertEqual(result.cad_brief, ["brief"])
        self.assertEqual(result.design_plan, ["plan"])
        self.assertEqual(result.code, "print(1)")
        self.assertEqual(result.validation_targets, ["target"])
        self.assertEqual(result.warnings, [])

    def test_response_text_from_responses_payload(self) -> None:
        payload = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"summary":"ok","code":"","warnings":[]}',
                        }
                    ]
                }
            ]
        }
        self.assertIn('"summary"', response_text(payload))

    def test_safety_blocks_network_and_destructive_calls(self) -> None:
        warnings = validate_generated_code("import urllib.request\nopen('/tmp/x', 'w')\n")
        self.assertIn("Blocked import: urllib.request", warnings)
        self.assertIn("Blocked call: open()", warnings)

    def test_safety_flags_obsolete_auto_smooth(self) -> None:
        warnings = validate_generated_code("mesh.use_auto_smooth = True\n")
        self.assertTrue(any("use_auto_smooth" in item for item in warnings))

    def test_cad_brief_extracts_dimensions_and_features(self) -> None:
        brief = build_cad_brief("Create a hollow screw cap for M38 5 cm top with knurl grip")
        joined = "\n".join(brief)
        self.assertIn("M38", joined)
        self.assertIn("50", joined)
        self.assertIn("hollow", joined)
        self.assertIn("knurl", joined)

    def test_cad_pipeline_flags_missing_constraints(self) -> None:
        failures = validate_cad_pipeline("create a screw cap for m38 5cm top", "import bpy\n")
        self.assertTrue(any("M38" in item for item in failures))
        self.assertTrue(any("50" in item for item in failures))
        self.assertTrue(any("metric" in item.lower() for item in failures))

    def test_cad_pipeline_accepts_metric_dimensioned_code(self) -> None:
        code = """
import bpy
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
CAP_DIAMETER_MM = 38
CAP_HEIGHT_MM = 50
THREAD_RIDGE = True
bpy.ops.mesh.primitive_cylinder_add(radius=19, depth=50)
"""
        failures = validate_cad_pipeline("create a screw cap for m38 5cm top", code)
        self.assertEqual(failures, [])

    def test_api_key_normalization(self) -> None:
        self.assertEqual(normalize_api_key("OPENAI_API_KEY='sk-test'\n"), "sk-test")
        self.assertIn("7 chars", api_key_fingerprint("sk-test"))
        self.assertIn("sk-proj-exam", api_key_fingerprint("sk-proj-example-CtpJ6cA"))
        self.assertIn("le-CtpJ6cA", api_key_fingerprint("sk-proj-example-CtpJ6cA"))


if __name__ == "__main__":
    unittest.main()
