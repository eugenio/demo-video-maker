# CLI Reference

The CLI is invoked via `demo-video-maker` (or `python -m demo_video_maker.cli`).

```bash
demo-video-maker [OPTIONS] COMMAND [ARGS]...
```

**Global options:**

| Option | Description |
|---|---|
| `-v`, `--verbose` | Enable debug logging |
| `--help` | Show help and exit |

---

## record

Full pipeline: load scenario, record browser, generate narration, stitch video.

```bash
demo-video-maker record SCENARIO_FILE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|---|---|
| `SCENARIO_FILE` | Path to the YAML scenario file (must exist) |

**Options:**

| Option | Type | Default | Description |
|---|---|---|---|
| `-o`, `--output` | PATH | `demo.mp4` | Output video file path |
| `--base-url` | TEXT | None | Override the scenario's `base_url` |
| `--tts` | `kokoro`/`openai`/`edge`/`silent` | `kokoro` | TTS backend |
| `--voice` | TEXT | None | TTS voice name (backend-specific) |
| `--mode` | `clip`/`screenshot` | `clip` | Recording mode |
| `--headed` | FLAG | off | Show browser window during recording |
| `--work-dir` | PATH | `.demo_build/<name>` | Working directory for build artifacts |
| `--gif` | FLAG | off | Also generate animated GIF preview |
| `--html` | FLAG | off | Also generate HTML tutorial |
| `--cursor`/`--no-cursor` | FLAG | on | Enable cursor overlay on click steps |
| `--gap` | FLOAT | `0.8` | Seconds of pause after narration (clip mode) |

**Examples:**

=== "Basic"

    ```bash
    demo-video-maker record scenarios/demo.yaml -o demo.mp4
    ```

=== "Edge TTS + GIF"

    ```bash
    demo-video-maker record scenarios/demo.yaml \
      --tts edge --voice en-US-AvaMultilingualNeural \
      --gif -o demo.mp4
    ```

=== "Screenshot mode"

    ```bash
    demo-video-maker record scenarios/demo.yaml \
      --mode screenshot --no-cursor -o demo.mp4
    ```

---

## capture

Capture screenshots only -- no TTS or video stitching. Produces a manifest and screenshot frames for later narration.

```bash
demo-video-maker capture SCENARIO_FILE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|---|---|
| `SCENARIO_FILE` | Path to the YAML scenario file (must exist) |

**Options:**

| Option | Type | Default | Description |
|---|---|---|---|
| `--base-url` | TEXT | None | Override the scenario's `base_url` |
| `--headed` | FLAG | off | Show browser window |
| `--work-dir` | PATH | `.demo_build/<name>` | Working directory |

**Example:**

```bash
demo-video-maker capture scenarios/demo.yaml --work-dir .demo_build/demo
```

---

## narrate

Add TTS narration to an existing manifest and produce a video. Use after `capture` to add voiceover.

```bash
demo-video-maker narrate MANIFEST_FILE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|---|---|
| `MANIFEST_FILE` | Path to the manifest JSON file (must exist) |

**Options:**

| Option | Type | Default | Description |
|---|---|---|---|
| `-o`, `--output` | PATH | `demo.mp4` | Output video file path |
| `--tts` | `kokoro`/`openai`/`edge`/`silent` | `kokoro` | TTS backend |
| `--voice` | TEXT | None | TTS voice name |
| `--gif` | FLAG | off | Also generate GIF preview |
| `--html` | FLAG | off | Also generate HTML tutorial |

**Example:**

```bash
demo-video-maker narrate .demo_build/demo/manifest.json \
  --tts openai --voice nova -o demo_narrated.mp4
```

---

## stitch

Re-stitch video from a manifest without regenerating narration. Use after manually editing step durations or audio offsets in `manifest.json` to fix audio-video sync issues.

```bash
demo-video-maker stitch MANIFEST_FILE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|---|---|
| `MANIFEST_FILE` | Path to the manifest JSON file (must exist) |

**Options:**

| Option | Type | Default | Description |
|---|---|---|---|
| `-o`, `--output` | PATH | `demo.mp4` | Output video file path |
| `--gif` | FLAG | off | Also generate GIF preview |
| `--html` | FLAG | off | Also generate HTML tutorial |
| `--gap` | FLOAT | `0.8` | Seconds of pause after narration (clip mode) |

**Example:**

```bash
demo-video-maker stitch .demo_build/demo/manifest.json \
  --gap 1.2 -o demo_fixed.mp4
```
