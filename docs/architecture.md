# Architecture

BlenderLLM-Plugin is split into two flat source folders:

```text
packages/                       Reusable core logic: OpenAI client, prompts, parsing, safety, validators.
plugins/                        Blender add-on logic: UI, operators, runtime execution, scene inspection.
scripts/
  build_blender_plugin.py        Bundles plugin + core into a Blender-installable zip.
tests/                          Pure Python tests with a small bpy stub.
docs/images/                    README screenshots.
dist/
  blenderllm_plugin-0.9.0.zip    Generated install artifact.
```

The repo source is intentionally flat: reusable core files live directly in `packages/`, and Blender add-on files live directly in `plugins/`. The builder packages those files into `blenderllm_plugin/` and `blenderllm_plugin/core/blenderllm_plugin_core/` inside the install zip, because Blender and Python still need package names at install time.

## Runtime Shape

Inside Blender, the installed add-on has this shape:

```text
blenderllm_plugin/
  __init__.py
  addon.py
  panel.py
  operators.py
  runtime.py
  inspection.py
  scene.py
  text_blocks.py
  core/
    blenderllm_plugin_core/
      client.py
      prompts.py
      models.py
      schema.py
      safety.py
      validators.py
```

`plugins/core_imports.py` hides the difference between development and installed mode. In development it imports from the flat `packages/` source. In Blender it imports from the bundled `blenderllm_plugin/core/blenderllm_plugin_core/` package.

## Main Flow

```text
Prompt
  -> CAD brief
  -> OpenAI structured response
  -> Static validation
  -> Static repair loop if needed
  -> Generated Python text block
  -> Apply
  -> Runtime execution
  -> Scene inspection
  -> Viewport snapshot
  -> Measured validation
  -> Runtime repair loop if needed
  -> Final CAD scene
```

## Step By Step

### 1. User Enters A Prompt

The user types a natural language CAD request in the Blender sidebar. The prompt can be short, such as:

```text
Create a hollow open-top enclosure with 3 mm walls and floor.
```

The state for the prompt, generated code, design plan, validation report, inspection report, and errors is stored on `bpy.types.Scene.blenderllm_plugin` in `plugins/properties.py`.

### 2. Local CAD Brief Extraction

Before calling OpenAI, `packages/validators.py` builds a local CAD brief from the prompt. It extracts things like:

```text
Units: millimeters
Dimensions: 3 mm walls, 2 mm fillets, M-size threads, cm-to-mm conversions
Features: holes, standoffs, fillets, shells, knurls, threads, ribs
Validation targets: dimensions and required feature checks
```

This gives the model a clearer contract and also gives the plugin local facts to validate later.

### 3. Optional Scene Context

If `Scene Context` is enabled, `plugins/scene.py` serializes the current Blender scene into compact JSON:

```text
object names
types
locations
rotations
scale
dimensions
mesh vertex and face counts
selected objects
unit system
```

This helps when modifying an existing scene, but it makes the request larger and slower. For brand-new parts, turning it off is usually faster.

### 4. Ask Starts A Background LLM Job

`plugins/operators.py` starts the OpenAI request in a background thread so Blender does not freeze while waiting for the response. The UI is updated through a modal timer.

The OpenAI request is handled by `packages/client.py` using the Responses API. The model is instructed by `packages/prompts.py` to return strict JSON, not loose prose.

### 5. Structured Response Parsing

The model response is parsed by `packages/models.py` into:

```text
summary
cad_brief
design_plan
code
validation_targets
warnings
```

The JSON shape is enforced by `packages/schema.py`.

### 6. Static Validation

Before the code is shown as ready, `packages/validators.py` and `packages/safety.py` check the generated Python for common problems:

```text
syntax errors
missing bpy usage
no mesh creation
unsafe imports or calls
obsolete Blender APIs
missing prompt dimensions
missing metric unit setup for physical CAD
missing named features such as holes, fillets, standoffs, threads, or knurls
```

This stage does not execute Blender code. It only inspects the text.

### 7. Static Repair Loop

If static validation fails and `Repairs` is greater than zero, the plugin asks the model to repair the code. The repair prompt includes:

```text
original prompt
CAD brief
current design plan
current code
validation failures
current scene context, if enabled
```

The model returns a complete replacement JSON response. The plugin repeats validation until the code passes or repair attempts run out.

### 8. Generated Code Is Stored In A Text Block

The final generated Python is stored in a Blender text block named:

```text
BlenderLLM-Plugin Generated.py
```

The user can open and edit this code before applying it.

### 9. Apply Executes On Blender's Main Thread

Generated code must run on Blender's main thread because it uses `bpy`. `plugins/runtime.py` handles execution.

Before execution, it normalizes common Blender API mistakes:

```text
mesh.use_auto_smooth is removed
primitive_cone_add(diameter1=...) -> radius1=diameter1 / 2
primitive_cone_add(diameter2=...) -> radius2=diameter2 / 2
primitive_cylinder_add(diameter=...) -> radius=diameter / 2
```

Then it runs the code with `bpy` available.

### 10. Post-Apply Scene Inspection

After Apply succeeds, `plugins/inspection.py` inspects the resulting Blender scene. It records:

```text
visible mesh count
new visible mesh count
object names
world-space bounding boxes
measured dimensions in scene units and millimeters
vertex counts
face counts
material counts
```

This moves the plugin closer to a deterministic CAD workflow: the system does not just trust that the code looks right, it measures what exists after execution.

### 11. Viewport Snapshot

The plugin attempts a best-effort OpenGL viewport snapshot using Blender's render operator. The snapshot is stored in the system temp directory:

```text
/tmp/blenderllm_plugin_snapshots/
```

If Blender cannot write the snapshot, the plugin records a snapshot status message instead of failing the whole Apply.

### 12. Measured Validation

The measured scene facts are checked against the prompt. For example:

```text
Prompt mentions 50 mm -> some measured object bound should be close to 50 mm
Prompt mentions 3 mm wall/floor -> code and scene should preserve that target
Prompt mentions cap/thread -> named cap/thread/ridge geometry should exist
Prompt mentions physical CAD -> scene should be metric
```

Measured validation is intentionally conservative. It catches obvious mismatches and missing geometry, but it does not replace a full CAD kernel.

### 13. Runtime Repair Loop

If Apply crashes or measured validation fails, the plugin starts another background OpenAI request. This repair request includes stronger evidence than the first pass:

```text
original prompt
CAD brief
current code
Python traceback, if execution failed
measured scene inspection report
scene inspection JSON
snapshot status/path
scene context, if enabled
```

The model returns replacement code. The plugin stores it in the generated text block and marks the pipeline as:

```text
Runtime repair ready to apply
```

The user clicks `Apply` again to execute the repaired code. This avoids running newly generated code automatically after a failure.

## Important Design Decisions

### Blender Execution Is Main-Thread Only

OpenAI requests run in background threads, but generated `bpy` code runs only from the Blender operator on the main thread. This keeps Blender API usage safer and avoids many UI freezes/crashes.

### Repair Produces Replacement Code

Repair prompts ask for complete replacement code, not patches. That keeps Blender text blocks simple and avoids trying to merge partial edits into generated Python.

### Validation Is Layered

The plugin uses several validation layers:

```text
static text/code validation before Apply
runtime exception handling during Apply
scene measurement validation after Apply
LLM repair using measured facts after failure
```

Each layer catches a different class of problem.

### The Repo Is Flat, The Zip Is Packaged

The source is flat to keep development simple. The zip is packaged because Blender requires an importable add-on module. `scripts/build_blender_plugin.py` bridges those two shapes.

## Key Files

```text
packages/client.py          OpenAI Responses API client.
packages/prompts.py         System prompt and repair prompt builders.
packages/models.py          Structured response parser.
packages/schema.py          Strict JSON schema for model output.
packages/safety.py          Static safety checks for generated Python.
packages/validators.py      CAD brief extraction and static CAD validation.
plugins/panel.py            Blender sidebar UI.
plugins/properties.py       Scene-level plugin state.
plugins/operators.py        Ask, Apply, repair, open-code, capture-scene, clear operators.
plugins/runtime.py          Blender code execution and API compatibility rewrites.
plugins/inspection.py       Post-Apply scene inspection, measurement checks, snapshots.
plugins/scene.py            Scene JSON capture.
plugins/text_blocks.py      Generated-code text block helpers.
scripts/build_blender_plugin.py  Builds the installable zip.
```
