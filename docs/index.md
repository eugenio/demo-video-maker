# demo-video-maker

Automated webapp demo video recorder powered by Playwright browser automation, text-to-speech narration, and FFmpeg video stitching.

## Key Features

- **Playwright browser automation** -- record any web application with click, type, scroll, hover, navigate, wait, and screenshot actions
- **4 TTS backends** -- Kokoro (local, no API key), OpenAI, Microsoft Edge TTS, and Silent mode for testing
- **FFmpeg video stitching** -- clip mode (live video per step) and screenshot mode (static frames) with automatic audio-video synchronization
- **MCP server** -- 10 tools, 3 resource templates, and 2 prompts for integration with Claude Code and other MCP clients
- **4 output formats** -- MP4 video, animated GIF preview, SRT/VTT subtitles, and interactive HTML tutorial
- **Cursor overlay** -- animated click cursor rendered via DOM injection (clip mode) or PNG compositing (screenshot mode)
- **Manifest-based workflow** -- capture once, re-narrate and re-stitch without re-recording

## Quick Install

```bash
pixi install && pixi run install && pixi run postinstall
```

## Quick Usage

```bash
demo-video-maker record scenario.yaml -o demo.mp4
```

## Documentation

| Section | Description |
|---|---|
| [Installation](getting-started/installation.md) | Prerequisites and install instructions |
| [Quick Start](getting-started/quickstart.md) | Record your first demo video |
| [CLI Reference](guide/cli.md) | All commands and options |
| [Scenario Format](guide/scenarios.md) | YAML scenario specification |
| [TTS Backends](guide/tts.md) | Voice synthesis configuration |
| [MCP Server](guide/mcp-server.md) | Tool server for AI assistants |
| [API Reference](api/models.md) | Python module documentation |
| [Architecture](architecture/overview.md) | System design and pipeline |
