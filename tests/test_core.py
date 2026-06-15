from __future__ import annotations

import unittest

from blenderllm_plugin_core import (
    api_key_fingerprint,
    normalize_api_key,
    parse_assistant_result,
    response_text,
    validate_cad_pipeline,
    validate_generated_code,
)


class CoreTests(unittest.TestCase):
    def test_parse_structured_response(self) -> None:
        result = parse_assistant_result(
            '{"summary":"ok","design_plan":["plan"],"code":"print(1)","validation_targets":["target"],"warnings":[]}'
        )
        self.assertEqual(result.summary, "ok")
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

    def test_cad_pipeline_flags_missing_constraints(self) -> None:
        failures = validate_cad_pipeline("create a screw cap for m38 5cm top", "import bpy\n")
        self.assertTrue(any("M38" in item for item in failures))
        self.assertTrue(any("50" in item for item in failures))

    def test_api_key_normalization(self) -> None:
        self.assertEqual(normalize_api_key("OPENAI_API_KEY='sk-test'\n"), "sk-test")
        self.assertIn("7 chars", api_key_fingerprint("sk-test"))
        self.assertIn("sk-proj-exam", api_key_fingerprint("sk-proj-example-CtpJ6cA"))
        self.assertIn("le-CtpJ6cA", api_key_fingerprint("sk-proj-example-CtpJ6cA"))


if __name__ == "__main__":
    unittest.main()
