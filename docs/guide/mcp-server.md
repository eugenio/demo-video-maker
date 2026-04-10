# MCP Server

demo-video-maker includes a Model Context Protocol (MCP) server built with FastMCP. This allows AI assistants like Claude Code to record demos, manage scenarios, and inspect builds programmatically.

## Starting the Server

```bash
demo-video-maker-mcp
```

Or via pixi:

```bash
pixi run mcp
```

The server runs over **stdio** transport.

## Claude Code Configuration

Add to your `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "demo-video-maker": {
      "type": "stdio",
      "command": "pixi",
      "args": ["run", "mcp"],
      "cwd": "/path/to/demo-video-maker"
    }
  }
}
```

---

## Tools

### Pipeline Tools

#### record_demo

Full pipeline: load scenario, record browser, generate narration, stitch video.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario_file` | string | **required** | Path to YAML scenario file |
| `output` | string | `demo.mp4` | Output video file path |
| `base_url` | string | None | Override scenario base_url |
| `tts` | string | `kokoro` | TTS backend (kokoro/openai/edge/silent) |
| `voice` | string | None | TTS voice name override |
| `mode` | string | `clip` | Recording mode (clip/screenshot) |
| `headed` | bool | false | Show browser window |
| `work_dir` | string | None | Working directory for artifacts |
| `gif` | bool | false | Generate GIF preview |
| `html` | bool | false | Generate HTML tutorial |
| `cursor` | bool | true | Enable cursor overlay (screenshot mode) |
| `gap` | float | 0.8 | Pause after narration in seconds (clip mode) |

**Returns:** `{status, video, manifest, extras}` or `{error}`

#### capture_screenshots

Capture screenshots from a scenario without narration or stitching.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario_file` | string | **required** | Path to YAML scenario file |
| `base_url` | string | None | Override scenario base_url |
| `headed` | bool | false | Show browser window |
| `work_dir` | string | None | Working directory |

**Returns:** `{status, manifest, frames_dir, frame_count}` or `{error}`

#### narrate_manifest

Add TTS narration to an existing manifest and produce a video.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `manifest_file` | string | **required** | Path to manifest JSON |
| `output` | string | `demo.mp4` | Output video file path |
| `tts` | string | `kokoro` | TTS backend |
| `voice` | string | None | TTS voice name |
| `gif` | bool | false | Generate GIF preview |
| `html` | bool | false | Generate HTML tutorial |

**Returns:** `{status, video, extras}` or `{error}`

#### stitch_video

Re-stitch video from a manifest without regenerating narration.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `manifest_file` | string | **required** | Path to manifest JSON |
| `output` | string | `demo.mp4` | Output video file path |
| `gif` | bool | false | Generate GIF preview |
| `html` | bool | false | Generate HTML tutorial |
| `gap` | float | 0.8 | Pause after narration in seconds |

**Returns:** `{status, video, extras}` or `{error}`

---

### Query Tools

#### list_scenarios

List available scenario YAML files in a directory. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenarios_dir` | string | `scenarios` | Directory to scan |

**Returns:** `{scenarios: [{name, path, title, step_count}]}`

#### validate_scenario

Validate a YAML scenario file and report any Pydantic validation errors. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario_file` | string | **required** | Path to YAML scenario file |

**Returns:** `{valid, errors, scenario}`

#### list_builds

List existing build directories that contain manifests. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `work_dir` | string | `.demo_build` | Root build directory |

**Returns:** `{builds: [{name, manifest_path, has_video, has_audio, step_count, title}]}`

#### get_manifest

Read and return the contents of a manifest JSON file. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `manifest_file` | string | **required** | Path to manifest JSON |

**Returns:** Full manifest data as a dictionary.

---

### Utility Tools

#### list_tts_voices

List available TTS voices for each backend. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `backend` | string | None | Filter to specific backend, or all |

**Returns:** `{backends: {name: {default, voices}}}`

#### get_scenario_details

Load a scenario YAML and return its full contents as structured data. Read-only.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario_file` | string | **required** | Path to YAML scenario file |

**Returns:** Full scenario data as a dictionary.

---

## Resources

Resource templates provide direct read access to project files.

| URI Template | MIME Type | Description |
|---|---|---|
| `scenario://{path}` | `text/yaml` | Raw YAML content of a scenario file |
| `manifest://{build_name}` | `application/json` | Manifest JSON from `.demo_build/{build_name}/manifest.json` |
| `build://{build_name}/video` | `text/plain` | Absolute path to a build's output MP4 |

**URI examples:**

```
scenario://scenarios/examples/basic_walkthrough.yaml
manifest://my_demo
build://my_demo/video
```

---

## Prompts

Prompts generate structured messages for AI assistant interactions.

### create_scenario

Generate a YAML scenario template for a web application demo.

| Parameter | Type | Description |
|---|---|---|
| `app_name` | string | Name of the web application |
| `base_url` | string | Base URL where the app is running |

Returns a formatted prompt with a YAML template, available actions, step field reference, and tips.

### debug_build

Analyze a build manifest to diagnose issues (missing frames, audio sync, duration problems).

| Parameter | Type | Description |
|---|---|---|
| `manifest_file` | string | Path to the manifest JSON file |

Returns the manifest data with a structured checklist of things to verify.
