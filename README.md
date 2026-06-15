# BlenderLLM-Plugin

BlenderLLM-Plugin is a Blender plugin inspired by the project structure of
`earthtojake/text-to-cad`: reusable AI/codegen logic lives under `packages/`,
Blender-specific integration lives under `plugins/`, and scripts build an
installable artifact.

The add-on gives you an LLM-style assistant inside Blender's 3D View sidebar.
It sends your prompt and optional scene context to OpenAI, receives a short
summary plus Blender Python, shows the generated code, and applies it to the
current scene when you approve.

## Project Structure

```text
packages/blenderllm_plugin_core/   Shared OpenAI, prompt, parsing, and safety logic
plugins/blenderllm_plugin/         Blender plugin source
scripts/build_blender_plugin.py    Blender zip builder
tests/                             Pure Python tests
docs/architecture.md               Layout notes
dist/                              Built plugin zips
```

## Build the Blender Plugin

```bash
python scripts/build_blender_plugin.py
```

The package is written to:

```text
dist/blenderllm_plugin-0.9.0.zip
```

## Install in Blender

1. Open Blender.
2. Go to `Edit > Preferences > Add-ons`.
3. Click `Install...` and choose `dist/blenderllm_plugin-0.9.0.zip`.
4. Enable `BlenderLLM-Plugin`.
5. Open the add-on preferences and paste your OpenAI API key, or launch Blender
   with `OPENAI_API_KEY` set.
6. Go to `Edit > Preferences > System > Network` and enable `Allow Online Access`.
7. In the 3D View, press `N` to open the sidebar, then use the `BlenderLLM` tab.

## Recommended Workflow

1. Type a prompt like: `Create a low-poly sci-fi desk lamp using the selected cube as the base.`
2. Keep `Scene Context` enabled when you want the assistant to inspect your current scene.
3. Click `Ask`.
4. Review or edit the generated Python in the `BlenderLLM-Plugin Generated.py` text block.
5. Click `Apply`.

Generated code runs inside Blender with access to `bpy`, so review code before
applying it when prompts involve destructive scene changes.

## Troubleshooting

### OpenAI requests fail in Blender

Enable `Edit > Preferences > System > Network > Allow Online Access`. The plugin
uses Blender's Python runtime to call the OpenAI API, so Blender must be allowed
to make network requests.

### Blender crashes in terminal before Python runs

If Blender opens normally from the app icon but crashes for terminal commands
like `Blender -b --python-expr "print('ok')"`, the plugin is not running yet.
That points to Blender startup, GPU/Metal, quarantine, or the installed Blender
build.

Try these in order:

1. Quit Blender and reopen it from `/Applications`.
2. In `Edit > Preferences > System`, set `Cycles Render Devices` to `None`.
3. Clear macOS quarantine metadata for Blender if it was downloaded through a browser:

   ```bash
   xattr -dr com.apple.quarantine /Applications/Blender.app
   ```

4. Replace Blender 4.2.0 with a newer official Apple Silicon build.

## Test

Run the pure Python tests with:

```bash
PYTHONPATH=packages/blenderllm_plugin_core python -m unittest
```

The Blender add-on entry point is:

```text
plugins/blenderllm_plugin/blenderllm_plugin/__init__.py
```

The builder bundles `plugins/blenderllm_plugin/blenderllm_plugin` and
`packages/blenderllm_plugin_core/blenderllm_plugin_core` into one installable top-level
`blenderllm_plugin/` folder. Generated artifacts and local experiments are not
shipped in the Blender install ZIP.
