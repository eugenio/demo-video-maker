# Pipeline

The recording pipeline runs in 5 phases. In clip mode, phase 1 runs before browser recording so that the recorder can hold each step for the correct narration duration.

## Phase 1: Pre-generate Audio (clip mode only)

```
Scenario steps --> TTSBackend.synthesize() --> MP3 files + duration map
```

The `pre_generate_audio()` function iterates over scenario steps, synthesizes narration for each step that has a `narration` field, and returns a dictionary mapping step index to `(audio_path, duration_seconds)`. This duration map is passed to the recorder so it knows how long to hold each step.

## Phase 2: Record Browser Session

```
Scenario --> Playwright (Chromium) --> frames/ + video/ + manifest.json
```

The `record_scenario()` function:

1. Launches a headless (or headed) Chromium browser via Playwright
2. In clip mode, enables Playwright's built-in video recording (`record_video_dir`)
3. Pre-navigates to the first URL to avoid a blank first frame
4. For each step:
    - Positions the DOM cursor on the target element (click/hover/type actions)
    - Executes the browser action (navigate, click, type, hover, scroll, wait)
    - Shows click pulse animation (click actions)
    - Applies element highlight if specified
    - Holds for `pause_between_steps` or `duration_override` (extended to fit narration in clip mode)
    - Captures a PNG screenshot
5. Saves the session video path on the first step result (clip mode)
6. Writes `manifest.json` with all step results

## Phase 3: Cursor Overlay (screenshot mode only)

```
manifest frames + CursorConfig --> ffmpeg overlay --> cursor-composited frames
```

The `apply_cursors_to_manifest()` function:

1. Generates cursor PNG files (normal and clicked) using pure Python
2. For each step with a `click_position`, composites the cursor onto the frame using ffmpeg's `overlay` filter
3. Updates `frame_path` in the manifest to point to the composited frame

In clip mode, cursor overlay is handled by DOM injection during recording (phase 2), so this phase is skipped.

## Phase 4: Generate Narration (screenshot mode) / Attach Audio (clip mode)

**Screenshot mode:**

```
manifest --> TTSBackend.synthesize() --> MP3 files + updated durations
```

The `generate_narration()` function synthesizes audio for each step and extends `step.duration` to fit the audio length (+ 0.5s padding).

**Clip mode:**

Pre-generated audio paths from phase 1 are attached to the manifest steps. No additional synthesis is needed.

## Phase 5: Stitch Final Video

The stitcher detects the mode automatically by checking for `video_path` entries in the manifest.

### Clip Mode Stitching

```
session video + per-step audio --> trimmed clips --> concat --> MP4
```

For each step:

1. Extract the video segment at the step's timestamp range from the session recording
2. Determine target duration: `audio_duration + transition_gap` (or minimum 2.0s if no audio)
3. If the extracted clip is shorter than the target, pad with the last frame using ffmpeg's `tpad` filter
4. Mux the step's narration audio onto the clip
5. Encode as H.264/AAC

All trimmed clips are concatenated using ffmpeg's concat demuxer with stream copy.

### Screenshot Mode Stitching

```
frames + concat file --> video track
per-step audio + adelay offsets --> merged audio track
video + audio --> MP4
```

1. Build a concat demuxer file listing each frame with its duration
2. Merge all per-step audio files into one track using ffmpeg's `adelay` filter to position each clip at the correct timeline offset, then `amix` to combine
3. Mux the video and audio tracks, trimming to the end of the last narration

## Data Flow

```
Scenario YAML
     |
     | Scenario.from_yaml()
     v
  Scenario
     |
     | record_scenario()
     v
  Manifest (frames + timing)
     |
     |--- apply_cursors_to_manifest()  [screenshot mode]
     |--- generate_narration()         [screenshot mode]
     |--- attach pre_audio             [clip mode]
     |
     v
  Manifest (frames + audio + timing)
     |
     | stitch_video()
     v
  MP4 video
     |
     |--- generate_srt() --> subtitles.srt
     |--- generate_vtt() --> subtitles.vtt
     |--- generate_gif() --> preview.gif
     |--- generate_html_tutorial() --> tutorial.html
     |--- export_narration_json() --> narration.json
```

## Build Directory Structure

```
.demo_build/<scenario_name>/
  manifest.json          # Central build manifest
  frames/
    step_000.png         # Per-step screenshots
    step_001.png
    ...
  audio/
    step_000.mp3         # Per-step narration audio
    step_001.mp3
    ...
  video/                 # Clip mode only
    <session>.webm       # Full session recording
  cursors/               # Screenshot mode only
    cursors/
      cursor.png         # Normal cursor image
      cursor_click.png   # Clicked cursor image
    cursor_step_001.png  # Composited frame
  trimmed_clips/         # Clip mode only
    step_000.mp4         # Per-step trimmed clips
    step_001.mp4
    ...
```
