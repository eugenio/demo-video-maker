# Demo Video Maker -- Operations Manual

> Playwright + TTS + FFmpeg = automated, scripted demo videos from YAML scenarios.

## What It Does

demo-video-maker records browser interactions via Playwright, overlays animated cursors,
generates AI narration (local or cloud TTS), and produces professional MP4 videos with
subtitles. Designed for product demos, tutorials, and walkthroughs.

---

## Prerequisites

| Tool        | Version  | Purpose                         |
|-------------|----------|---------------------------------|
| pixi        | latest   | Environment & dependency mgmt  |
| Python      | >= 3.11  | Runtime                         |
| FFmpeg      | >= 6.0   | Video/audio processing          |
| Chromium    | (auto)   | Browser engine via Playwright   |

## Installation

```bash
# 1. Clone and enter the project
cd /home/uge/demo-video-maker

# 2. Install all dependencies
pixi install

# 3. Install Python package in editable mode
pixi run install

# 4. Install Chromium for Playwright
pixi run postinstall
```

## First-Run Note

The first time you use `--tts kokoro`, the Kokoro ONNX model (~200 MB) is downloaded
and cached to `~/.cache/kokoro-onnx/`. Subsequent runs are instant.

---

## CLI Commands Reference

### `record` -- Full Pipeline (capture + narrate + stitch)

```bash
pixi run record SCENARIO.yaml [OPTIONS]
```

| Option            | Default                  | Description                                |
|-------------------|--------------------------|--------------------------------------------|
| `-o, --output`    | `demo.mp4`               | Output video path                          |
| `--base-url`      | from YAML                | Override the scenario's base_url           |
| `--tts`           | `kokoro`                 | TTS backend: kokoro, openai, edge, silent  |
| `--voice`         | backend-dependent        | Voice name (see TTS Backends below)        |
| `--headed`        | off                      | Show browser window during recording       |
| `--work-dir`      | `.demo_build/<name>`     | Working directory for intermediate files   |
| `--gif`           | off                      | Also generate animated GIF preview         |
| `--html`          | off                      | Also generate interactive HTML tutorial    |
| `--cursor/--no-cursor` | cursor on           | Enable/disable cursor overlay              |
| `-v, --verbose`   | off                      | Debug logging                              |

**Pipeline phases:**
1. Record -- Playwright captures each step as PNG screenshot
2. Cursor -- SVG cursor overlaid on click steps via FFmpeg
3. Narrate -- TTS backend generates MP3 for each narration
4. Stitch -- FFmpeg concat demuxer + audio merge produces MP4
5. Extras -- SRT, VTT, GIF, HTML, narration.json

### `capture` -- Screenshots Only

```bash
pixi run -- python -m demo_video_maker.cli capture SCENARIO.yaml [OPTIONS]
```

| Option        | Description                       |
|---------------|-----------------------------------|
| `--base-url`  | Override scenario base_url        |
| `--headed`    | Show browser window               |
| `--work-dir`  | Output directory for frames       |

Produces `manifest.json` + `frames/` directory. No TTS, no video.

### `narrate` -- Add Narration to Existing Frames

```bash
pixi run -- python -m demo_video_maker.cli narrate MANIFEST.json [OPTIONS]
```

| Option        | Description                       |
|---------------|-----------------------------------|
| `-o, --output`| Output MP4 path                   |
| `--tts`       | TTS backend                       |
| `--voice`     | Voice name                        |
| `--gif`       | Also generate GIF                 |
| `--html`      | Also generate HTML tutorial       |

Use this to iterate on voice/narration without re-recording the browser.

---

## TTS Backends

### Kokoro (recommended -- local, no API key)

| Voice       | Gender | Accent  | Quality |
|-------------|--------|---------|---------|
| af_heart    | F      | US      | A       |
| af_bella    | F      | US      | A-      |
| af_nicole   | F      | US      | B-      |
| am_michael  | M      | US      | C+      |
| am_fenrir   | M      | US      | C+      |
| bf_emma     | F      | British | B-      |
| bm_george   | M      | British | B-      |
| if_sara     | F      | Italian | C       |
| im_nicola   | M      | Italian | C       |

Languages: en-us, en-gb, it, fr, es, ja, zh, hi, pt-br

### OpenAI (cloud -- requires OPENAI_API_KEY)

Voices: onyx, alloy, echo, fable, nova, shimmer
Models: tts-1, tts-1-hd

```bash
export OPENAI_API_KEY="sk-..."
pixi run record scenario.yaml --tts openai --voice nova
```

### Edge TTS (free cloud -- no API key)

Default voice: en-US-AvaMultilingualNeural
100+ language-specific voices available.

### Silent (no audio)

Generates silence proportional to text length (~2.5 words/sec).
Use for testing or when adding audio externally.

---

## YAML Scenario Format

```yaml
title: "Demo Title"                  # Required
base_url: "http://localhost:8080"    # Root URL (default)
resolution: [1920, 1080]            # Viewport (default: 1920x1080)
pause_between_steps: 1.5            # Frame hold duration in seconds
voice: "onyx"                       # Default voice

steps:
  - action: navigate                # Go to URL
    url: /path
    narration: "Spoken text for this step"
    wait_for: "body"                # Wait for selector before screenshot

  - action: click                   # Click element
    selector: ".button-class"
    narration: "Click here to open the menu."
    highlight: ".button-class"      # Blue outline before screenshot

  - action: type                    # Fill text input
    selector: "#search-input"
    text: "search query"
    narration: "Type your search term."

  - action: scroll                  # Scroll page
    distance: 500                   # Pixels to scroll down

  - action: hover                   # Hover over element
    selector: ".tooltip-trigger"

  - action: wait                    # Pause
    wait_seconds: 3.0

  - action: screenshot              # Explicit screenshot
    narration: "Overview of the current state."
```

### Action Types

| Action       | Required Fields      | Description                    |
|--------------|---------------------|--------------------------------|
| `navigate`   | `url`               | Go to URL (relative to base)   |
| `click`      | `selector`          | Click CSS element              |
| `type`       | `selector`, `text`  | Fill text into input           |
| `scroll`     | `distance`          | Scroll page by N pixels        |
| `hover`      | `selector`          | Hover over element             |
| `wait`       | `wait_seconds`      | Sleep for N seconds            |
| `screenshot` | (none)              | Take explicit screenshot       |

### Optional Step Fields

| Field               | Description                              |
|---------------------|------------------------------------------|
| `narration`         | Text-to-speech narration for this step   |
| `highlight`         | CSS selector -- draws blue outline       |
| `wait_for`          | CSS selector -- wait before screenshot   |
| `duration_override` | Override pause_between_steps (seconds)   |

---

## Output Files

After `pixi run record scenario.yaml -o demo.mp4 --gif --html`:

| File                | Format    | Description                              |
|---------------------|-----------|------------------------------------------|
| `demo.mp4`          | H.264+AAC | Final video (1 FPS, faststart)          |
| `subtitles.srt`     | SRT       | Subtitles for video players              |
| `subtitles.vtt`     | WebVTT    | Subtitles for web players                |
| `narration.json`    | JSON      | Timing data (startMs, endMs, text)       |
| `preview.gif`       | GIF       | Animated preview (if --gif)              |
| `tutorial.html`     | HTML      | Interactive step-by-step (if --html)     |

### Build Artifacts (`.demo_build/<name>/`)

| Directory/File   | Purpose                                   |
|------------------|-------------------------------------------|
| `frames/`        | Raw PNG screenshots (1920x1080)           |
| `cursors/`       | SVG cursor templates                      |
| `cursor_*.png`   | Cursor-overlaid frames                    |
| `audio/`         | Per-step MP3 narration files              |
| `manifest.json`  | Recording metadata (JSON)                 |
| `concat.txt`     | FFmpeg concat demuxer file                |

---

## Common Workflows

### Workflow 1: Quick demo with local TTS

```bash
pixi run record scenarios/examples/protein_platform.yaml \
  -o protein_demo.mp4 \
  --tts kokoro \
  --voice af_heart
```

### Workflow 2: Iterate on narration without re-recording

```bash
# Step 1: Capture frames only
pixi run -- python -m demo_video_maker.cli capture scenarios/examples/protein_platform.yaml

# Step 2: Try different voices
pixi run -- python -m demo_video_maker.cli narrate .demo_build/protein_platform/manifest.json \
  -o v1_bella.mp4 --tts kokoro --voice af_bella

pixi run -- python -m demo_video_maker.cli narrate .demo_build/protein_platform/manifest.json \
  -o v2_michael.mp4 --tts kokoro --voice am_michael
```

### Workflow 3: Full output suite

```bash
pixi run record scenarios/examples/protein_platform.yaml \
  -o demo.mp4 --gif --html --tts kokoro
```

### Workflow 4: Debug with visible browser

```bash
pixi run record scenarios/examples/basic_walkthrough.yaml \
  -o test.mp4 --headed --tts silent
```

---

## Troubleshooting

| Problem                              | Solution                                         |
|--------------------------------------|--------------------------------------------------|
| "Chromium not found"                 | Run `pixi run postinstall`                       |
| Kokoro first run slow                | Model download (~200 MB), cached afterward       |
| Black frames in video                | Add `wait_for: "body"` to navigate steps         |
| Audio out of sync                    | Step duration auto-adjusts; check narration text |
| FFmpeg not found                     | `pixi install` installs ffmpeg via conda-forge   |
| OPENAI_API_KEY not set               | `export OPENAI_API_KEY="sk-..."` before run      |
| Wrong resolution                     | Set `resolution: [1920, 1080]` in YAML           |

## Development

```bash
pixi run test       # Run unit tests
pixi run lint       # Ruff linting
pixi run format     # Ruff formatting
pixi run typecheck  # mypy strict checking
```
