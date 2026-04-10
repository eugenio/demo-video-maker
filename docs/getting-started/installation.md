# Installation

## Prerequisites

| Dependency | Minimum Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| FFmpeg | 6+ | Video/audio processing |
| Chromium | Latest | Browser automation (installed via Playwright) |

## Install with pixi (recommended)

```bash
pixi install
pixi run install
pixi run postinstall
```

This installs the Python package in editable mode, pulls all dependencies, and downloads Chromium for Playwright.

## Install with pip

```bash
pip install -e .
playwright install chromium
```

!!! note "FFmpeg required"
    FFmpeg must be available on your `PATH`. On Ubuntu/Debian: `sudo apt install ffmpeg`. On macOS: `brew install ffmpeg`.

## Optional Dependencies

For development (linting, testing, type checking):

```bash
pip install -e '.[dev]'
```

## Verify Installation

```bash
demo-video-maker --help
```

Expected output:

```
Usage: demo-video-maker [OPTIONS] COMMAND [ARGS]...

  Automated webapp demo video recorder.

Options:
  -v, --verbose  Enable debug logging
  --help         Show this message and exit.

Commands:
  capture  Capture screenshots only (no TTS or video stitching).
  narrate  Add narration to existing screenshots and produce video.
  record   Record a demo video from a YAML scenario file.
  stitch   Re-stitch video from manifest without regenerating narration.
```

## MCP Server

The MCP server is installed as a separate entry point:

```bash
demo-video-maker-mcp
```

Or via pixi:

```bash
pixi run mcp
```
