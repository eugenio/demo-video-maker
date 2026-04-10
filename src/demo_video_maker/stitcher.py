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
            "-show_format", str(media_path),
        ],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


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


def _merge_audio_tracks(manifest: Manifest, work_dir: Path) -> Path | None:
    """Merge per-step audio files into a single track with correct timing.

    Uses FFmpeg's adelay filter to position each narration clip at the correct
    offset in the timeline.

    Args:
        manifest: Recording manifest with audio paths.
        work_dir: Working directory for temporary files.

    Returns:
        Path to the merged audio file, or None if no audio exists.
    """
    audio_steps = [s for s in manifest.steps if s.audio_path]
    if not audio_steps:
        return None

    merged_path = work_dir / "narration_merged.mp3"

    # Calculate cumulative time offsets
    offsets: list[float] = []
    cumulative = 0.0
    for step in manifest.steps:
        if step.audio_path:
            offsets.append(cumulative)
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
    return merged_path


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

    Returns:
        Path to the created video file.
    """
    if work_dir is None:
        work_dir = output_path.parent / ".stitcher_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_video_clips(manifest):
        return _stitch_clips(manifest, output_path, work_dir)
    return _stitch_frames(manifest, output_path, work_dir, fps)


def _stitch_clips(manifest: Manifest, output_path: Path, work_dir: Path) -> Path:
    """Overlay narration audio onto the session video recording.

    The session video is a single .webm recorded by Playwright. Narration
    audio tracks are positioned at cumulative step timestamps using the
    adelay filter, then mixed and muxed with the video.

    Args:
        manifest: Recording manifest with session video and audio paths.
        output_path: Output MP4 path.
        work_dir: Working directory for temp files.

    Returns:
        Path to the created video file.
    """
    session_video = _get_session_video(manifest)
    if not session_video:
        logger.warning("No session video found, falling back to frame stitching")
        return _stitch_frames(manifest, output_path, work_dir, fps=1)

    audio_track = _merge_audio_tracks(manifest, work_dir)

    cmd = ["ffmpeg", "-y", "-i", str(session_video)]

    if audio_track:
        cmd.extend(["-i", str(audio_track)])

    cmd.extend([
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
    ])

    if audio_track:
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
    else:
        cmd.extend(["-an"])

    cmd.extend(["-movflags", "+faststart", str(output_path)])

    logger.info("Stitching session video + narration to %s", output_path)
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
    audio_track = _merge_audio_tracks(manifest, work_dir)

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
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.extend([
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ])

    logger.info("Stitching video to %s", output_path)
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("Video created: %s", output_path)
    return output_path
