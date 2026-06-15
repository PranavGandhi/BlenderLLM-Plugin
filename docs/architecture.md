# Architecture

This repo follows a plugin-first layout inspired by `earthtojake/text-to-cad`.

```text
packages/
  blenderllm_plugin_core/      Shared OpenAI, prompt, parsing, and safety logic.
plugins/
  blenderllm_plugin/           Blender add-on source.
scripts/
  build_blender_plugin.py  Bundles plugin + core into a Blender-installable zip.
tests/
  test_core.py             Pure Python tests for reusable core logic.
dist/
  blenderllm_plugin-0.9.0.zip  Generated install artifact.
```

The Blender add-on imports a bundled copy of `blenderllm_plugin_core` from
`blenderllm_plugin/core/blenderllm_plugin_core` inside the zip. That keeps installation
simple for Blender users while preserving reusable code boundaries in the repo.

The plugin layer owns Blender UI, scene capture, text blocks, add-on
preferences, and generated code execution. The core package owns OpenAI request
formatting, structured response parsing, prompt construction, and lightweight
safety checks.
