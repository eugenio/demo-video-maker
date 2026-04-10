"""FFmpeg video composition from frames/clips and narration audio."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from demo_video_maker.models import Manifest

logger = logging.getLogger(__name__)


def _get_duration(media_path: Path) -> float:
    """Get duration of a media file in seconds via ffprobe.

    Args:
        media_path: Path to audio or video file.

    Returns:
        Duration in seconds.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams", str(media_path),
        ],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    # Prefer format duration, fall back to longest stream duration (webm compat)
    if "duration" in info.get("format", {}):
        return float(info["format"]["duration"])
    for stream in info.get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    return 0.0


def _build_concat_file(manifest: Manifest, work_dir: Path) -> Path:
    """Build an FFmpeg concat demuxer input file from screenshot frames.

    Args:
        manifest: Recording manifest with step frames and durations.
        work_dir: Working directory for temporary files.

    Returns:
        Path to the concat file.
    """
    concat_path = work_dir / "concat.txt"
    with open(concat_path, "w") as f:
        for step in manifest.steps:
            abs_path = Path(step.frame_path).resolve()
            f.write(f"file '{abs_path}'\n")
            f.write(f"duration {step.duration}\n")
        # FFmpeg concat requires the last file to be listed again
        if manifest.steps:
            abs_path = Path(manifest.steps[-1].frame_path).resolve()
            f.write(f"file '{abs_path}'\n")
    return concat_path


def _get_session_video(manifest: Manifest) -> Path | None:
    """Find the session video path stored in the manifest.

    Args:
        manifest: Recording manifest.

    Returns:
        Path to the session video, or None if not present.
    """
    for step in manifest.steps:
        if step.video_path:
            p = Path(step.video_path)
            if p.exists():
                return p
    return None


def _merge_audio_tracks(manifest: Manifest, work_dir: Path) -> tuple[Path, float] | None:
    """Merge per-step audio files into a single track with correct timing.

    Uses FFmpeg's adelay filter to position each narration clip at the correct
    offset in the timeline.

    Args:
        manifest: Recording manifest with audio paths.
        work_dir: Working directory for temporary files.

    Returns:
        Tuple of (merged audio path, end time of last narration in seconds),
        or None if no audio exists.
    """
    audio_steps = [s for s in manifest.steps if s.audio_path]
    if not audio_steps:
        return None

    merged_path = work_dir / "narration_merged.mp3"

    # Calculate time offsets: use audio_offset if set, otherwise cumulative
    offsets: list[float] = []
    cumulative = 0.0
    for step in manifest.steps:
        if step.audio_path:
            offsets.append(step.audio_offset if step.audio_offset is not None else cumulative)
        cumulative += step.duration

    # Build FFmpeg filter graph
    inputs: list[str] = []
    filter_parts: list[str] = []
    for i, (step, offset_sec) in enumerate(zip(audio_steps, offsets, strict=True)):
        inputs.extend(["-i", str(Path(step.audio_path).resolve())])
        delay_ms = int(offset_sec * 1000)
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_steps)))
    filter_parts.append(f"{mix_inputs}amix=inputs={len(audio_steps)}:normalize=0[aout]")
    filter_graph = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_graph,
        "-map", "[aout]",
        "-ac", "2", "-ar", "44100",
        str(merged_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # Calculate when the last narration ends
    last_end = 0.0
    for step, offset in zip(audio_steps, offsets, strict=True):
        audio_dur = _get_duration(Path(step.audio_path))
        last_end = max(last_end, offset + audio_dur)

    return merged_path, last_end


def _has_video_clips(manifest: Manifest) -> bool:
    """Check if the manifest contains video clip paths.

    Args:
        manifest: Recording manifest to check.

    Returns:
        True if any step has a video_path set.
    """
    return any(s.video_path for s in manifest.steps)


def stitch_video(
    manifest: Manifest,
    output_path: Path,
    *,
    work_dir: Path | None = None,
    fps: int = 1,
    transition_gap: float = 0.8,
) -> Path:
    """Combine frames or video clips with narration into a final MP4.

    Automatically detects whether the manifest contains video clips
    (from --mode clip) or only screenshots, and uses the appropriate
    stitching strategy.

    Args:
        manifest: Recording manifest with frames/clips and optional audio.
        output_path: Path for the output MP4 file.
        work_dir: Working directory for temp files. Defaults to output parent.
        fps: Frames per second for screenshot mode.
        transition_gap: Seconds of pause after narration ends before
            cutting to the next step (clip mode only).

    Returns:
        Path to the created video file.
    """
    if work_dir is None:
        work_dir = output_path.parent / ".stitcher_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_video_clips(manifest):
        return _stitch_clips(manifest, output_path, work_dir, transition_gap)
    return _stitch_frames(manifest, output_path, work_dir, fps)


def _stitch_clips(
    manifest: Manifest, output_path: Path, work_dir: Path, transition_gap: float,
) -> Path:
    """Cut per-step clips from session video, trim to narration + gap, and concat.

    For each step:
      1. Extract the video segment at the step's timestamp range
      2. Trim it to audio_duration + transition_gap (or a minimum if no audio)
      3. If the extracted clip is shorter, pad with the last frame
      4. Overlay the step's narration audio
      5. Concatenate all trimmed clips into the final video

    Args:
        manifest: Recording manifest with session video and audio paths.
        output_path: Output MP4 path.
        work_dir: Working directory for temp files.
        transition_gap: Seconds after narration before cutting to next step.

    Returns:
        Path to the created video file.
    """
    session_video = _get_session_video(manifest)
    if not session_video:
        logger.warning("No session video found, falling back to frame stitching")
        return _stitch_frames(manifest, output_path, work_dir, fps=1)

    clips_dir = work_dir / "trimmed_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Calculate each step's start time in the session video
    step_starts: list[float] = []
    cumulative = 0.0
    for step in manifest.steps:
        step_starts.append(step.audio_offset if step.audio_offset is not None else cumulative)
        cumulative += step.duration

    session_dur = _get_duration(session_video)
    min_step_dur = 2.0  # minimum duration for steps without narration

    concat_entries: list[str] = []

    for i, step in enumerate(manifest.steps):
        clip_path = clips_dir / f"step_{i:03d}.mp4"
        ss = step_starts[i]

        # Available video for this step
        next_ss = step_starts[i + 1] if i + 1 < len(manifest.steps) else session_dur
        available = next_ss - ss

        # Target duration: narration + gap, or minimum
        if step.audio_path and Path(step.audio_path).exists():
            audio_dur = _get_duration(Path(step.audio_path))
            target_dur = audio_dur + transition_gap
        else:
            target_dur = min(step.duration, min_step_dur + transition_gap)

        # Don't exceed available video (but we can pad with last frame)
        extract_dur = min(available, target_dur)

        # Build ffmpeg command to extract + pad + mux audio
        cmd = ["ffmpeg", "-y", "-ss", f"{ss:.3f}", "-i", str(session_video)]

        if step.audio_path and Path(step.audio_path).exists():
            cmd.extend(["-i", str(Path(step.audio_path).resolve())])

        # Video filter: pad with last frame if needed, then scale
        vf_parts = []
        if target_dur > extract_dur + 0.1:
            pad = target_dur - extract_dur
            vf_parts.append(f"tpad=stop_mode=clone:stop_duration={pad:.3f}")
        vf_parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        cmd.extend([
            "-t", f"{target_dur:.3f}",
            "-vf", ",".join(vf_parts),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        ])

        if step.audio_path and Path(step.audio_path).exists():
            cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-an"])

        cmd.append(str(clip_path))
        subprocess.run(cmd, check=True, capture_output=True)

        concat_entries.append(f"file '{clip_path.resolve()}'")
        logger.debug("Step %d: %.1fs video (%.1fs audio + %.1fs gap)", i, target_dur,
                      target_dur - transition_gap, transition_gap)

    # Concat all trimmed clips
    concat_file = work_dir / "trimmed_concat.txt"
    concat_file.write_text("\n".join(concat_entries))

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c:v", "copy", "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("Stitching %d trimmed clips to %s", len(manifest.steps), output_path)
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("Video created: %s", output_path)
    return output_path


def _stitch_frames(
    manifest: Manifest, output_path: Path, work_dir: Path, fps: int,
) -> Path:
    """Stitch screenshot frames with merged audio into a final MP4.

    Args:
        manifest: Recording manifest with frames and audio.
        output_path: Output MP4 path.
        work_dir: Working directory for temp files.
        fps: Frames per second.

    Returns:
        Path to the created video file.
    """
    concat_file = _build_concat_file(manifest, work_dir)
    result = _merge_audio_tracks(manifest, work_dir)
    audio_track, audio_end = result if result else (None, 0.0)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
    ]

    if audio_track:
        cmd.extend(["-i", str(audio_track)])

    cmd.extend([
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-r", str(fps),
    ])

    if audio_track:
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-t", f"{audio_end:.2f}"])

    cmd.extend([
        "-movflags", "+faststart",
        str(output_path),
    ])

    logger.info("Stitching video to %s", output_path)
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("Video created: %s", output_path)
    return output_path
