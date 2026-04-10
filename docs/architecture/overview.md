# Architecture Overview

## High-Level Pipeline

```
Scenario YAML
     |
     v
 +----------+     +-----------+     +----------+     +-------+
 | Recorder |---->| Manifest  |---->| Narrator |---->|Stitcher|----> MP4
 +----------+     +-----------+     +----------+     +-------+
   Playwright       JSON file        TTS audio        FFmpeg
   browser          (frames,         per step         concat +
   automation       timing,                           audio mix
                    narration)
                        |
                        +---> Subtitles (SRT/VTT)
                        +---> GIF preview
                        +---> HTML tutorial
                        +---> Narration JSON
```

## Module Responsibilities

| Module | Purpose |
|---|---|
| `models` | Pydantic data models: `Scenario`, `Step`, `Manifest`, `StepResult`, `CursorConfig`, `OutputConfig` |
| `recorder` | Playwright browser automation: executes steps, captures screenshots, records video clips |
| `narrator` | TTS synthesis with pluggable backends: `KokoroTTS`, `OpenAITTS`, `EdgeTTS`, `SilentBackend` |
| `stitcher` | FFmpeg video composition: frame concatenation, clip trimming, audio mixing |
| `cursor` | Cursor overlay: PNG generation (pure Python, no Pillow) and ffmpeg compositing |
| `subtitles` | SRT and WebVTT subtitle generation from manifest timing |
| `gif` | Animated GIF generation using ffmpeg palettegen/paletteuse pipeline |
| `tutorial` | Self-contained HTML tutorial with step screenshots, narration, navigation, lightbox |
| `narration_export` | Narration timing JSON export (DemoSmith-compatible format) |
| `cli` | Click-based CLI with 4 commands: `record`, `capture`, `narrate`, `stitch` |
| `mcp_server` | FastMCP server: 10 tools, 3 resources, 2 prompts for AI assistant integration |

## Design Principles

**Manifest-based workflow.** The manifest JSON file is the central artifact. It links frames to audio paths, stores timing data, and enables re-narration and re-stitching without re-recording the browser session. Every pipeline stage reads from and writes to the manifest.

**Pluggable TTS.** All TTS backends implement the `TTSBackend` abstract class with a single `synthesize(text, output_path)` method. New backends can be added by subclassing `TTSBackend` and registering in the backend map.

**Direct FFmpeg.** Video processing uses subprocess calls to `ffmpeg` and `ffprobe` rather than Python wrappers. This avoids dependency bloat and gives full control over the encoding pipeline.

**Two recording modes.** Clip mode records the entire browser session as a single WebM video and extracts per-step clips at stitch time. Screenshot mode captures static PNG frames and concatenates them. Clip mode produces smoother output; screenshot mode is faster and uses less disk space.

**Zero external image dependencies.** The cursor module generates PNG files using pure Python (`struct` + `zlib`) without Pillow, Cairo, or any imaging library. FFmpeg handles all compositing.
