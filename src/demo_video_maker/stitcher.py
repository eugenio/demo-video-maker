"""FFmpeg video composition from frames and narration audio."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from demo_video_maker.models import Manifest

logger = logging.getLogger(__name__)


def _build_concat_file(manifest: Manifest, work_dir: Path) -> Path:
    """Build an FFmpeg concat demuxer input file.

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


def stitch_video(
    manifest: Manifest,
    output_path: Path,
    *,
    work_dir: Path | None = None,
    fps: int = 1,
) -> Path:
    """Combine screenshot frames and narration into a final MP4.

    Args:
        manifest: Recording manifest with frames and optional audio.
        output_path: Path for the output MP4 file.
        work_dir: Working directory for temp files. Defaults to output parent.
        fps: Frames per second for the output video.

    Returns:
        Path to the created video file.
    """
    if work_dir is None:
        work_dir = output_path.parent / ".stitcher_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)

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
