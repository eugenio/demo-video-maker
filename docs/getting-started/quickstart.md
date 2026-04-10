# Quick Start

Record your first demo video in under 5 minutes.

## 1. Create a Scenario

Create a file called `my_demo.yaml`:

```yaml
title: "My First Demo"
base_url: "http://localhost:8080"
resolution: [1920, 1080]
pause_between_steps: 2.0

steps:
  - action: navigate
    url: /
    narration: "Welcome to the application."
    wait_for: "body"

  - action: click
    selector: "#get-started"
    narration: "Click Get Started to begin."
    highlight: "#get-started"

  - action: screenshot
    narration: "Here is the main dashboard."
```

## 2. Record the Video

```bash
demo-video-maker record my_demo.yaml -o demo.mp4
```

This runs the full pipeline:

1. Pre-generates narration audio (Kokoro TTS by default)
2. Launches headless Chromium and records the browser session
3. Applies cursor overlays on click steps
4. Stitches the final MP4 with synchronized narration

## 3. Check the Output

The command produces:

```
demo.mp4              # Final video
subtitles.srt         # SRT subtitles
subtitles.vtt         # WebVTT subtitles
narration.json        # Narration timing data
```

Build artifacts are stored in `.demo_build/<scenario_name>/`:

```
.demo_build/my_demo/
  manifest.json       # Build manifest (frames, audio paths, timing)
  frames/             # Per-step screenshots (PNG)
  audio/              # Per-step narration files (MP3)
  video/              # Session recording (WebM, clip mode only)
```

## 4. Re-stitch Without Re-recording

Edit timing in `manifest.json`, then re-stitch:

```bash
demo-video-maker stitch .demo_build/my_demo/manifest.json -o demo_v2.mp4
```

## Common Options

```bash
# Use a different TTS backend
demo-video-maker record my_demo.yaml --tts edge --voice en-US-AvaMultilingualNeural

# Screenshot mode instead of clip mode
demo-video-maker record my_demo.yaml --mode screenshot

# Show the browser window during recording
demo-video-maker record my_demo.yaml --headed

# Generate GIF and HTML tutorial as extras
demo-video-maker record my_demo.yaml --gif --html
```

## Next Steps

- [CLI Reference](../guide/cli.md) -- all commands and options
- [Scenario Format](../guide/scenarios.md) -- complete YAML specification
- [TTS Backends](../guide/tts.md) -- voice configuration
